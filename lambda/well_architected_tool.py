import json
import boto3
import os
import uuid
import base64
import fitz
import tempfile

class WellArchitectedTool:
    def __init__(self, region_name):
        self.client = boto3.client('wellarchitected', region_name=region_name)
        self.s3_client = boto3.client('s3')
        self.sns_client = boto3.client('sns')


    def upload_custom_lens(self, lens_json, lens_version):
        lens_name = lens_json['name']
        
        # Get existing lens information if available
        existing_lens_arn, existing_lens_status, existing_lens_version = self.get_lens_info(lens_name)
        
        # Handle different statuses of the existing lens
        if existing_lens_arn:
            if existing_lens_status == 'DRAFT':
                print(f"Draft lens '{lens_name}' already exists. Publishing lens. Lens ARN: {existing_lens_arn}")
                try:
                    self.publish_lens(existing_lens_arn, lens_version)
                    print(f"Draft lens '{lens_name}' published successfully. Lens ARN: {existing_lens_arn}")
                except Exception as e:
                    print(f"Error publishing draft lens '{lens_name}': {e}")
                return existing_lens_arn
            elif existing_lens_status == 'PUBLISHED' and existing_lens_version == lens_version:
                print(f"Published lens '{lens_name}' with the same version already exists. Lens ARN: {existing_lens_arn}")
                return existing_lens_arn
            elif existing_lens_status == 'PUBLISHED' and existing_lens_version != lens_version:
                print(f"Published lens '{lens_name}' with a different version exists. Deleting and recreating...")
                self.unapply_lens_from_workloads(existing_lens_arn)
                self.delete_lens(existing_lens_arn)

        # Import and publish the new lens
        try:
            response = self.client.import_lens(
                JSONString=json.dumps(lens_json),
                ClientRequestToken='custom-lens-upload-' + str(uuid.uuid4())
            )
            lens_arn = response['LensArn']
            print(f"Custom lens '{lens_name}' uploaded successfully. Lens ARN: {lens_arn}")
            self.publish_lens(lens_arn, lens_version)
            return lens_arn
        except self.client.exceptions.ValidationException as e:
            if "A lens with normalized name" in str(e):
                print(f"Lens '{lens_name}' with normalized name already exists and cannot be recreated immediately.")
            else:
                print(f"Validation error when importing lens '{lens_name}': {e}")
            return None
        except Exception as e:
            print(f"Error uploading custom lens '{lens_name}': {e}")
            return None

    def unapply_lens_from_workloads(self, lens_arn):
        try:
            response = self.client.list_workloads()
            workloads = response['WorkloadSummaries']
            for workload in workloads:
                workload_id = workload['WorkloadId']
                if lens_arn in workload['Lenses']:
                    print(f"Removing lens {lens_arn} from workload {workload_id}...")
                    self.client.disassociate_lenses(WorkloadId=workload_id, LensAliases=[lens_arn])
                    print(f"Lens {lens_arn} removed from workload {workload_id}.")
        except Exception as e:
            print(f"Error removing lens {lens_arn} from workloads: {e}")

    def publish_lens(self, lens_arn, lens_version):
        try:
            response = self.client.create_lens_version(
                LensAlias=lens_arn,
                ClientRequestToken='publish-lens-' + str(uuid.uuid4()),
                LensVersion=lens_version
            )
            print(f"Lens {lens_arn} published successfully. Lens version: {response['LensVersion']}")
        except Exception as e:
            print(f"Error publishing lens {lens_arn}: {e}")

    def get_lens_info(self, lens_name):
        next_token = None
        while True:
            response = self.client.list_lenses(NextToken=next_token) if next_token else self.client.list_lenses()
            for lens in response['LensSummaries']:
                if lens['LensName'] == lens_name:
                    return lens['LensArn'], lens['LensStatus'], lens['LensVersion']
            next_token = response.get('NextToken')
            if not next_token:
                break
        return None, None, None

    def delete_lens(self, lens_arn):
        try:
            self.client.delete_lens(LensAlias=lens_arn)
            print(f"Lens '{lens_arn}' deleted successfully.")
        except Exception as e:
            print(f"Error deleting lens '{lens_arn}': {e}")

    def get_workload_id_by_name(self, workload_name):
        response = self.client.list_workloads()
        for workload in response['WorkloadSummaries']:
            if workload['WorkloadName'] == workload_name:
                return workload['WorkloadId']
        return None

    def create_workload(self, workload_name, environment='PRODUCTION', lenses=None, review_owner='', aws_regions=None, workload_description=''):
        if lenses is None:
            lenses = []
        if aws_regions is None:
            aws_regions = []
        response = self.client.create_workload(
            WorkloadName=workload_name,
            Description=workload_description,
            Environment=environment,
            Lenses=lenses,
            ReviewOwner=review_owner,
            AwsRegions=aws_regions
        )
        workload_id = response['WorkloadId']
        print(f"\nWorkload created: {workload_id}")
        return workload_id

    def create_or_update_lens_review(self, workload_id, lens_arn):
        try:
            self.client.update_lens_review(
                WorkloadId=workload_id,
                LensAlias=lens_arn
            )
            print(f"\nLens review created or updated for workload {workload_id} and lens {lens_arn}")
        except self.client.exceptions.ValidationException as e:
            if "No lens review for lens alias" in str(e):
                print(f"\nNo lens review found for workload {workload_id} and lens {lens_arn}. Associating lens...")
                try:
                    self.client.associate_lenses(
                        WorkloadId=workload_id,
                        LensAliases=[lens_arn]
                    )
                    print(f"\nLens {lens_arn} associated with workload {workload_id}")
                    self.create_or_update_lens_review(workload_id, lens_arn)
                except self.client.exceptions.ValidationException as assoc_e:
                    print(f"\nError associating lens {lens_arn} with workload {workload_id}: {assoc_e}")
                    if "User might be not authorized to access lens" in str(assoc_e):
                        print("\nAuthorization issue detected. Please check permissions.")
                        return
            else:
                print(f"\nError creating or updating lens review for workload {workload_id} and lens {lens_arn}: {e}")
        except Exception as e:
            print(f"\nError creating or updating lens review for workload {workload_id} and lens {lens_arn}: {e}")

    def update_workload(self, workload_id, lens_arn, answers_data):
        try:
            for question_response in answers_data['questionResponses']:
                question_id = question_response['questionId']
                choices = question_response['choices']
                try:
                    response = self.client.update_answer(
                        WorkloadId=workload_id,
                        LensAlias=lens_arn,
                        QuestionId=question_id,
                        SelectedChoices=choices
                    )
                    print(f"Question '{question_id}' updated for workload: {response['WorkloadId']}")
                except Exception as e:
                    print(f"Error updating question '{question_id}' for workload {workload_id}: {e}")
        except Exception as e:
            print(f"Error updating workload {workload_id} with lens {lens_arn}: {e}")

    def generate_report(self, workload_id, lens_arn,bucket_name,wa_pdf,sns_topic_arn):
        try:
            response = self.client.get_lens_review_report(
                WorkloadId=workload_id,
                LensAlias=lens_arn
            )
            report_data = response['LensReviewReport']['Base64String']
            pdf_data = base64.b64decode(report_data)
            s3_key = wa_pdf
            self.s3_client.put_object(Bucket=bucket_name, Key=s3_key, Body=pdf_data)
            print(f"Well-Architected report generated and uploaded to s3://{bucket_name}/{s3_key}")

            # Publish SNS notification
            message = f"Well-Architected report generated and uploaded to s3://{bucket_name}/{s3_key}"
            self.sns_client.publish(
                TopicArn=sns_topic_arn,
                Message=message,
                Subject='Well-Architected Report Available'
            )
            print("SNS notification sent.")           
        except self.client.exceptions.ValidationException as e:
            if "No lens review for lens alias" in str(e):
                print(f"No lens review found for workload {workload_id} and lens {lens_arn}. Creating a new lens review...")
                self.create_or_update_lens_review(workload_id, lens_arn)
                self.generate_report(workload_id, lens_arn,bucket_name,wa_pdf,sns_topic_arn)
            else:
                print(f"Error generating report for workload {workload_id} and lens {lens_arn}: {e}")
        except Exception as e:
            print(f"Error generating report for workload {workload_id} and lens {lens_arn}: {e}")           

    def mask_pdf(self, bucket, account_number,wa_pdf,wa_pdf_masked):
        # Download the PDF file from S3 to a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            self.s3_client.download_fileobj(bucket, wa_pdf, temp_file)
            temp_file_path = temp_file.name
        document = fitz.open(temp_file_path)
        for page_num in range(len(document)):
            page = document[page_num]
            text_instances = page.search_for(account_number)
            for inst in text_instances:
                page.add_redact_annot(inst, text='XXXXXXXXXXXXX', fill=(0, 0, 0))
            page.apply_redactions()
        document.save(f"/tmp/{wa_pdf_masked}")
        document.close()

        # Read the masked PDF as bytes
        with open(f"/tmp/{wa_pdf_masked}", 'rb') as masked_pdf:
            pdf_bytes = masked_pdf.read()

        # Upload the masked PDF to S3
        self.s3_client.put_object(Bucket=bucket, Key=wa_pdf_masked, Body=pdf_bytes)
        print(f"Well-Architected report with masked account number saved to s3://{bucket}/{wa_pdf_masked}")


def handler(event, context):
    region_name = os.getenv('REGION')
    account_number = os.getenv('ACCOUNT')
    lens_version = os.getenv('LENS_VERSION')
    lens_name = os.getenv('LENS_NAME')
    workload_name = os.getenv('WORKLOAD_NAME')
    workload_description = os.getenv('WORKLOAD_DESCRIPTION')
    review_owner = os.getenv('REVIEW_OWNER')
    custom_lens_file = os.getenv('CUSTOM_LENS_FILENAME')
    answers_file = os.getenv('ANSWERS_FILENAME')
    wa_pdf = os.getenv('WA_PDF')
    wa_pdf_masked = os.getenv('WA_PDF_MASKED')
    sns_topic_arn = os.getenv('SNS_TOPIC_ARN')

    tool = WellArchitectedTool(region_name)

    # Iterate through the uploaded files
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        # Download the object from S3
        s3_client = boto3.client('s3')
        download_path = f'/tmp/{key}'
        s3_client.download_file(bucket, key, download_path)

        if key == custom_lens_file:
            # process the custom lens
            with open(download_path, 'r') as lens_file:
                lens_json = json.load(lens_file)
                tool.upload_custom_lens(lens_json, lens_version)

        if key == answers_file:
            # Process the answers
            with open(download_path, 'r') as answers_file:
                answers_json = json.load(answers_file)
                # Get lens information if available
                lens_arn, lens_status, lens_version = tool.get_lens_info(lens_name)
            
                if lens_arn:
                    workload_id = tool.get_workload_id_by_name(workload_name)
                    if not workload_id:
                        workload_id = tool.create_workload(workload_name, lenses=[lens_arn], review_owner=review_owner, aws_regions=[region_name], workload_description=workload_description)
                    else:
                        tool.create_or_update_lens_review(workload_id, lens_arn)
                    tool.update_workload(workload_id, lens_arn, answers_json)
                    tool.generate_report(workload_id, lens_arn,bucket,wa_pdf,sns_topic_arn)
                    tool.mask_pdf(bucket, account_number,wa_pdf, wa_pdf_masked)


