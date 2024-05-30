import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';


export class WellArchitectedToolStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 bucket to store custom lens JSON files
    const bucket = new s3.Bucket(this, 'CustomLensBucket', {
      bucketName: 'well-architect-custom-lens-demo',
      versioned: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true
    });

    // IAM role for the Lambda function
    const lambdaRole = new iam.Role(this, 'LambdaExecutionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonS3FullAccess'),
        iam.ManagedPolicy.fromAwsManagedPolicyName('WellArchitectedConsoleFullAccess')  // Custom policy for WA Tool access
      ]
    });

    const fitzLayer = new lambda.LayerVersion(this, 'FitzLayer', {
      code: lambda.Code.fromAsset('layer/fitz-layer.zip'),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_9],
      
      description: 'Layer containing the fitz (PyMuPDF) library',
    });

    // Lambda function triggered by S3 upload
    const fn = new lambda.Function(this, 'CustomLensHandler', {
        functionName: 'well_architected_tool',
        runtime: lambda.Runtime.PYTHON_3_9,
        code: lambda.Code.fromAsset('lambda'),
        architecture: lambda.Architecture.X86_64,
        handler: 'well_architected_tool.handler',
        role: lambdaRole,
        timeout: cdk.Duration.seconds(30),
        layers: [fitzLayer],
        environment: {
            'REGION': this.region,
            'ACCOUNT': this.account,
            'LENS_NAME': 'Sample Lens',
            'LENS_VERSION': '1.0',
            'WORKLOAD_NAME': 'My Workload',
            'WORKLOAD_DESCRIPTION': 'My Workload Description',
            'REVIEW_OWNER': 'your_review_owner_email@example.com',
            'CUSTOM_LENS_FILENAME': 'custom_lens.json',
            'ANSWERS_FILENAME': 'answers.json',
            'WA_PDF': 'well-architected-report.pdf',
            'WA_PDF_MASKED': 'well-architected-report-masked.pdf'
        }
    });

    // Adding S3 bucket notification to trigger Lambda on object creation
    bucket.addEventNotification(s3.EventType.OBJECT_CREATED, new s3n.LambdaDestination(fn));
  }
}
