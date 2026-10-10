# Run LeakLens locally with real AWS storage

The website and model run on your Mac. Saved analyses and generated household models
are stored in Amazon S3. Maintenance tickets, profiles, notification preferences,
inbox entries and findings are stored in DynamoDB. Optional email alerts use Amazon SES.
This setup does not host the website on EC2 and does not need CloudShell.

## Run

From the project root, use the existing virtual environment:

```bash
.venv/bin/python deploy/run_aws_local.py
```

Open http://127.0.0.1:8000/#/ . Stop another backend using port 8000 with Ctrl+C
before starting this one. The launcher reads explicit saved AWS settings, checks
your account and a DynamoDB read, and starts the backend with AWS mode enabled.
It does not silently fall back to SQLite. It removes unrelated credential environment
variables from the child process so the configured profile is actually used.

For a connection check without starting the website:

```bash
.venv/bin/python deploy/run_aws_local.py --check
```

## Local configuration and permissions

`.aws/leaklens-local.json` holds the bucket, table, region, profile, configured sender,
recipient and local website URL. It contains no AWS access keys, and the whole `.aws/`
directory is excluded from Git and deployment bundles. This file is necessary because
shell exports are lost when starting the app from another terminal.

The `leaklens-local` IAM user has the reviewed runtime policy in
`.aws/local-app-policy.json`: S3 GetObject/PutObject only under this app's `analyses/`
and `models/` prefixes, DynamoDB GetItem/PutItem/Scan only on its records table,
and SES SendEmail only from the configured identity to the configured recipient.
It also has AWS-managed SignInLocalDevelopmentAccess and IAMUserChangePassword
policies for temporary browser login and changing its own password.
There are no permanent AWS access keys or app infrastructure/admin permissions.

The baseline policy was generated using AWS IAM Policy Autopilot from
`backend/storage.py` and `backend/notifications.py`, then narrowed to the actual
resources and operations. Unused replication, customer-KMS, access-point, object
variant, Object Lambda and SES template permissions were removed.

The root profile is retained for account administration. The app uses `leaklens-app`,
which delegates credential export to the `leaklens-limited` browser-login profile.
The launcher validates both `AWS_ACCOUNT_ID` and `AWS_APP_USER` before starting.
For a new installation, create `.aws/leaklens-local.json` using your own non-secret resource details:

```json
{
  "AWS_ACCOUNT_ID": "123456789012",
  "AWS_APP_USER": "leaklens-local",
  "AWS_PROFILE": "leaklens-app",
  "AWS_REGION": "ap-south-1",
  "LEAKLENS_BUCKET": "your-private-leaklens-bucket",
  "LEAKLENS_TABLE": "leaklens-records",
  "LEAKLENS_EMAIL_FROM": "verified-sender@example.com",
  "LEAKLENS_EMAIL_TO": "verified-recipient@example.com",
  "LEAKLENS_PUBLIC_URL": "http://127.0.0.1:8000"
}
```

After completing the limited user's browser login, configure the SDK bridge once:

```bash
aws configure set credential_process 'aws configure export-credentials --profile leaklens-limited --format process' --profile leaklens-app
aws configure set region ap-south-1 --profile leaklens-app
```

Temporary credentials are cached by AWS CLI outside the repository, not written
into the frontend or uploaded CSVs.

## Refresh sign-in

When the temporary session expires, renew `leaklens-limited` through AWS CLI's
browser login, selecting the limited IAM user. Restart the app afterward if needed.
Do not replace this profile with the account root login.
See https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html .

For another developer or AWS account, create their own resources and local JSON
configuration rather than copying credentials. An EC2 deployment instead uses the
instance-role workflow in `AWS_STEPS.md`; the laptop's `.aws/` files are never bundled.

## Verify the actual integration

1. `/api/health` must report `aws_enabled: true` and `Amazon S3 + DynamoDB`.
2. Analyse an attributed demo CSV and create a maintenance ticket.
3. Verify an object named `analyses/<analysis_id>.json.gz` in S3 and a
   `ticket#<ticket_id>` record in DynamoDB using the administrator console.
4. Report the synthetic repair and upload its follow-up file; refresh/restart the
   server and confirm the ticket and result can still be read from AWS.
5. Test a new household model if demonstrating profiles: its generated artifact
   must round-trip from `models/` in S3 and its metadata from DynamoDB.
6. For email, verify the configured SES email address in the same region, enable
   email in Notifications, and analyse a file with previously unseen episodes.
   Check that SES accepts it and separately confirm inbox delivery.

Existing SQLite records are not automatically migrated. Old browser session links
to local analyses may need a fresh upload after switching storage modes.

## Costs, retention and cleanup

This setup uses the existing S3 bucket, on-demand DynamoDB table and SES account.
It adds no EC2 instance, public IP, RDS database, dedicated IP or production access
request. Usage consumes eligible Free Tier credits; inspect Billing before scaling.
The manual bucket has no automatic expiration unless you add a lifecycle rule.
The CloudFormation deployment's 30-day expiry is a separate configuration.
Retain demo records for judging, then remove only this app's records/resources when
you no longer need them. Do not delete unrelated AWS data.

Keep the S3 bucket private with Block Public Access and SSE-S3 encryption, use TLS
for AWS API access, and keep runtime permissions limited. For a public production
deployment, add application access controls and HTTPS; consider encrypted access
logging, CloudTrail data events and CloudWatch monitoring after checking their cost.
This local prototype has no household ownership or user login for website visitors.

## Files and why they exist

- `deploy/run_aws_local.py`: one reliable command to launch AWS mode without repeated exports.
- `deploy/AWS_LOCAL.md`: these setup, sign-in, verification and cleanup instructions.
- `.aws/leaklens-local.json`: private machine configuration required by the launcher.
- `.aws/local-app-policy.json`: the exact reviewed permissions attached to the app user.
- `.aws/console-login.txt`: the temporary first-sign-in password, required only until
  you change it. Never commit it; the password is not an AWS access key.
- `.aws/aws-verification.json`: private evidence from live AWS integration checks.

GitHub publishing remains a separate next step.
