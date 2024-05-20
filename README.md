# waf-custom-lens-automation

# Architecture Diagram

```mermaid
graph TD;
    A[S3 Bucket] -->|S3 Event Notification| B[Lambda Function];
    B -->|Process JSON| C[AWS Well-Architected Tool];
    B -->|Download JSON| A;
    B -.->|Assume Role| D[IAM Role];
    D --> B;
    X[User] --> |File Upload| A[S3 Bucket];
