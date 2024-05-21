# Automating the AWS Well-Architected Tool using a Custom Lens

# Architecture Diagram

```mermaid
graph TD;
    A[S3 Bucket] -->|S3 Event Notification| B[Lambda Function];
    B -->|Process JSON| C[AWS Well-Architected Tool];
    B -->|Download JSON| A;
    B -.->|Assume Role| D[IAM Role];
    D --> B;
    X[User] --> |File Upload| A[S3 Bucket];
    C -->|Create Workload| E[Workload];
    C -->|Apply Lens| F[Lens Review];
    C -->|Answer Questions| G[Question Answers];
    C -->|Generate Report| H[Report PDF in S3];
    H -->|Uploaded Report| A;

     
# Usage
1. To upload the custom lens:
aws s3 cp custom_lens.json s3://well-architect-custom-lens-demo/

2. To upload the answers, create workload, reivew answers and generate Well-Architected PDF Report:
aws s3 cp answers.json s3://well-architect-custom-lens-demo/


The cdk.json file tells the CDK Toolkit how to execute your app.

Useful commands

npm run build compile typescript to js
npm run watch watch for changes and compile
npm run test perform the jest unit tests
npx cdk deploy deploy this stack to your default AWS account/region
npx cdk diff compare deployed stack with current state
npx cdk synth emits the synthesized CloudFormation template