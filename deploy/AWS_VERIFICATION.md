# Live AWS integration verification

Verified on 10 October 2026 in ap-south-1 using the limited LeakLens IAM user.
The website and model service run locally on the demonstration laptop. AWS supplies
real S3 storage, DynamoDB records, and SES email. EC2/public website hosting has not
been deployed. GitHub publishing is the separate next step.

## Verified with the running application and real AWS APIs

- `/api/health` reports AWS mode and Amazon S3 + DynamoDB.
- The laptop profile resolves to the limited `leaklens-local` IAM user; the launcher
  rejects root credentials. Browser sign-in supplies temporary credentials with no
  permanent AWS access keys embedded in the app.
- An attributed synthetic demo CSV produces alert episodes. Its saved compressed
  analysis round-trips through S3 with SSE-S3/AES256 encryption.
- Creating the same maintenance ticket twice returns one ticket. Investigation,
  an explicitly undetermined finding, a reported synthetic repair, and a follow-up
  comparison are saved to DynamoDB. Direct AWS reads match the app's responses.
- The follow-up outcome is `improved`, with complete 96-interval comparison windows,
  90 alert intervals before and zero after. This demonstrates an artificial flow
  being removed, not a confirmed physical repair or measured water savings.
- An update carrying a stale revision returns HTTP 409.
- Re-uploading the same observed episodes does not generate another notification.
- Email preferences and the notification inbox persist in DynamoDB. SES accepted
  the alert, and the recipient separately confirmed inbox delivery.
- The `aws-demo` sample household profile is saved in DynamoDB. Its generated model
  is saved under `models/` in encrypted S3, loaded back, and used for analysis. Its
  baseline is relabelled sample data for a storage test, not an independent real home.
- After stopping and restarting the backend, the saved source analysis, ticket,
  follow-up result, household profile, email preferences, inbox, and household model
  remain accessible from AWS; the model is reloaded successfully.
- All 16 Python workflow/adapter tests pass. The refreshed deployment bundle contains
  no private AWS settings, password file, local database, or raw dataset.

## Resource setup and limits

The configured S3 bucket is private with all Block Public Access controls enabled
and default SSE-S3 encryption. The DynamoDB table is active with String partition
key `pk` and on-demand capacity. SES uses a verified email-address identity in the
same region, with the same verified address as sender and recipient. SES remains
in its sandbox; no production access or paid upgrade was requested.

The account's Free plan was confirmed active with USD 100 credits at setup; these
are eligible usage credits, not a promise of indefinite free service. The current
manual bucket has no automatic lifecycle expiry. The optional CloudFormation
template's 30-day analysis expiry belongs to a separate hosting deployment.

Runtime permissions are scoped to this application's S3 `analyses/` and `models/`
objects, DynamoDB table, and SES sender/recipient. AWS-managed login and self-password
change policies support the IAM user's browser sign-in. The exact reviewed policy,
resource names and live test IDs are in ignored `.aws/` files, not this public report.

No EC2, RDS, public IP, load balancer, or HTTPS endpoint was provisioned. A public
hosted deployment remains optional and would require a separate deployment decision,
cost review and application access controls. Existing SQLite records were not
automatically migrated. Email processing still uses in-process background tasks.

## Run the verified configuration

From the project root, run:

```bash
.venv/bin/python deploy/run_aws_local.py
```

Open http://127.0.0.1:8000/#/ . Stop the existing server first if port 8000 is occupied.
Renew the limited browser-login profile when its temporary session expires.
Use `--check` to test the configured identity and DynamoDB read without starting a server.
See [AWS_LOCAL.md](AWS_LOCAL.md) for configuration, credential refresh and cleanup.
