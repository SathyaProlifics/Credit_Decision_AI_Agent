# Deploying the stop-EC2 Lambda (SAM)

Files added:
- stop_ec2_lambda.py
- template.yaml

Quick deploy (using AWS SAM CLI):

1. Install and configure AWS CLI credentials and SAM CLI.

2. Edit `template.yaml` to set `TARGET_INSTANCE_ID` under `Environment/Variables` OR provide it during deployment.

3. Build and deploy:

```bash
sam build
sam deploy --guided
```

During `sam deploy --guided` you can set the `TARGET_INSTANCE_ID` as a parameter via environment variables or update the stack after deploy.

Alternative: deploy via `aws cloudformation deploy` after packaging with `sam package` if desired.

Invocation notes:
- EventBridge schedule triggers the function automatically per `Schedule` in `template.yaml`.
- You can also invoke the Lambda manually and pass `{"instance_id": "i-012345..."}` or `{"instance_ids": ["i-..","i-.."]}` in the event JSON.

IAM notes:
- The template grants `ec2:StopInstances` and `ec2:DescribeInstances` on all resources. Tighten the resource ARNs to your account/instance ARNs for least privilege.
