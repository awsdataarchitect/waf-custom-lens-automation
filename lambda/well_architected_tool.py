import json
import boto3
import os
import uuid

class WellArchitectedTool:
    def __init__(self, region_name):
        self.client = boto3.client('wellarchitected', region_name=region_name)

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

def handler(event, context):
    region_name = os.getenv('REGION')
    lens_version = '1.0'
    tool = WellArchitectedTool(region_name)

    # Iterate through the uploaded files
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        # Download the lens JSON file from S3
        s3_client = boto3.client('s3')
        download_path = f'/tmp/{key}'
        s3_client.download_file(bucket, key, download_path)

        # Upload the custom lens
        with open(download_path, 'r') as lens_file:
            lens_json = json.load(lens_file)
            tool.upload_custom_lens(lens_json, lens_version)

