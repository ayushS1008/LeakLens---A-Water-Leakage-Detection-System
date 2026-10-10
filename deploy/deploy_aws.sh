#!/usr/bin/env bash
# Run in AWS CloudShell after uploading the bundle, template, and this script.
set -euo pipefail
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-ap-south-1}}"
STACK_NAME="${LEAKLENS_STACK_NAME:-leaklens-demo}"
ALLOW_HTTP_FROM="${LEAKLENS_HTTP_CIDR:-0.0.0.0/0}"
for filename in leaklens-deploy.zip cloudformation.json; do
  if [[ ! -f "$filename" ]]; then
    echo "Missing $filename. Upload the three deployment files to this CloudShell directory."
    exit 1
  fi
done
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" >/dev/null 2>&1; then
  echo "Stack $STACK_NAME already exists. Use a new LEAKLENS_STACK_NAME, or inspect the existing deployment."
  exit 1
fi
ARTIFACT_BUCKET="leaklens-build-${ACCOUNT_ID}-${REGION}-$(date +%s)"
echo "This creates an EC2 instance, networking, S3 buckets, and a DynamoDB table in $REGION. Charges may apply beyond your AWS credits."
if [[ "$REGION" == "us-east-1" ]]; then
  aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION"
else
  aws s3api create-bucket --bucket "$ARTIFACT_BUCKET" --region "$REGION" --create-bucket-configuration "LocationConstraint=$REGION"
fi
aws s3api put-public-access-block --bucket "$ARTIFACT_BUCKET" --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3 cp leaklens-deploy.zip "s3://$ARTIFACT_BUCKET/leaklens-deploy.zip" --sse AES256
printf '%s\n' "$ARTIFACT_BUCKET" > leaklens-artifact-bucket.txt
aws cloudformation deploy --region "$REGION" --stack-name "$STACK_NAME" --template-file cloudformation.json --capabilities CAPABILITY_IAM --parameter-overrides "ArtifactBucket=$ARTIFACT_BUCKET" "AllowedHttpCidr=$ALLOW_HTTP_FROM" "EmailSender=${LEAKLENS_EMAIL_FROM:-}" "EmailRecipient=${LEAKLENS_EMAIL_TO:-}"
aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs' --output json > leaklens-stack-outputs.json
cat leaklens-stack-outputs.json
APP_URL="$(aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK_NAME" --query 'Stacks[0].Outputs[?OutputKey==`AppUrl`].OutputValue | [0]' --output text)"
echo "Infrastructure created. Waiting for the app to finish installing…"
for attempt in $(seq 1 90); do
  if curl --fail --silent --max-time 8 "$APP_URL/api/health"; then
    echo
    echo "Open $APP_URL"
    echo "Keep leaklens-stack-outputs.json and leaklens-artifact-bucket.txt for your demo and cleanup."
    exit 0
  fi
  sleep 5
done
echo "App is not ready yet. Use EC2 > Connect > Session Manager and inspect: sudo journalctl -u leaklens; sudo tail -n 100 /var/log/cloud-init-output.log"
exit 1
