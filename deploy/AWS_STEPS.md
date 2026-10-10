> For the verified laptop website with real S3, DynamoDB and SES, use [AWS_LOCAL.md](AWS_LOCAL.md). The instructions below describe optional EC2 hosting, which has not been deployed. Live results are in [AWS_VERIFICATION.md](AWS_VERIFICATION.md).

# Finish the AWS deployment

These files prepare an AWS deployment; they do not create an account or deploy by themselves.

## 1. Account

Create and activate an account at https://portal.aws.amazon.com/billing/signup . Check the AWS Free Tier / credit balance in Billing before deployment. This deployment creates billable resources; free coverage depends on your account, usage, and credits.

Sign into the AWS console, choose one region (for example Mumbai / ap-south-1), and open **CloudShell** from the console toolbar. Use its temporary signed-in credentials; do not put access keys in the repository.

## 2. Build locally

In VS Code's frontend terminal, stop Vite with Ctrl+C if needed:

```bash
cd /Users/ayushsaxena/Desktop/leaklens/frontend
npm run build
```

In a new project-root terminal:

```bash
cd /Users/ayushsaxena/Desktop/leaklens
source .venv/bin/activate
python deploy/build_bundle.py
```

The bundle is `build/leaklens-deploy.zip`. It contains the built React app, Python backend, saved model and settings, runtime requirements, and licence notices. It excludes credentials, private local tickets, the virtual environment, and raw datasets.

## 3. Upload three files to CloudShell

Choose **Actions > Upload file** for each file:

1. `build/leaklens-deploy.zip`
2. `deploy/cloudformation.json`
3. `deploy/deploy_aws.sh`

Run in CloudShell:

```bash
bash deploy_aws.sh
```

Allow several minutes. The script uploads a private artifact and creates a CloudFormation stack named `leaklens-demo`. It prints the application URL when `/api/health` responds. An existing stack is not overwritten automatically.

The deployment uses a t3.micro EC2 instance with Ubuntu 24.04, an Nginx proxy, private S3 analysis storage, and a pay-per-request DynamoDB records table. The app uses an instance role with permissions limited to its bucket, artifact, and table. Python dependencies use the same pinned scikit-learn version as the saved model.

The HTTP demo has no login. Use the provided synthetic sample files and keep the deployment short-lived. For access restricted to your address, set `LEAKLENS_HTTP_CIDR` to your public IPv4 address followed by `/32` before running the script. A production version needs user authentication and HTTPS.

## 4. Verify and demonstrate AWS

1. Open the printed URL. The Maintenance panel should show **Amazon S3 + DynamoDB**.
2. Analyse `data/demo/leak_before_repair.csv` from your Mac.
3. Create a ticket, report the synthetic repair time from `data/demo/demo_instructions.json`, and upload `followup_after_repair.csv` in that ticket.
4. Refresh the page; the ticket should remain.
5. In the AWS console, open the output **DataBucket**. Show the object under `analyses/`.
6. Open the output **TicketsTable** in DynamoDB and **Explore table items**. Show an item with `pk` starting `ticket#`; its JSON body includes the status and follow-up result.
7. Show the EC2 instance and deployed app URL in the demo video.

These live checks are required before claiming successful AWS integration. The local mode and stubbed adapter tests do not prove cloud deployment.

## Troubleshooting

- See CloudFormation stack **Events** for infrastructure failures.
- If the app is not ready, use EC2 **Connect > Session Manager**:
  `sudo tail -n 100 /var/log/cloud-init-output.log`
  `sudo journalctl -u leaklens -n 100`
- `/api/health` should report `aws_enabled: true`.
- A storage error must be fixed in AWS permissions/configuration; the app intentionally does not fall back silently to local storage.
- Original analysis objects expire after 30 days. Verify repairs while the source object is still available.

## Cleanup after judging

Save anything you need before cleanup. Deleting the CloudFormation stack terminates the instance and removes its networking and role. The **DataBucket** and **TicketsTable** are intentionally retained to prevent accidental record loss; delete them separately when you no longer need the data. The artifact bucket named in `leaklens-artifact-bucket.txt` is also separate; empty and delete it when finished. Retained resources can continue incurring charges.

Do not terminate the app before the submission/demo checks are complete.

References: https://docs.aws.amazon.com/cloudshell/latest/userguide/working-with-aws-cloudshell.html ; https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/quickref-ec2-instance-config.html ; https://ubuntu.com/aws/docs/aws-how-to/instances/find-ubuntu-images/ ; https://docs.aws.amazon.com/boto3/latest/guide/credentials.html

## Optional email notifications with AWS SES

Email code is included, but it does not send until you configure SES and explicitly enable it in **Notifications**. There is no AWS account or verified sender bundled with the project.

1. In your chosen AWS region, open Amazon SES and verify two **email-address identities**: the sender and recipient. Complete the verification links from both inboxes. The supplied IAM policy targets the sender email identity; domain-only verification requires adjusting that policy to the domain identity ARN. While SES is in its sandbox, recipients must also be verified. See [SES SendEmail requirements](https://docs.aws.amazon.com/ses/latest/APIReference/API_SendEmail.html).
2. Before running the deployment script in CloudShell, set `LEAKLENS_EMAIL_FROM` and `LEAKLENS_EMAIL_TO` to those addresses. The script passes them as optional stack parameters. The role grants `ses:SendEmail` for that sender and recipient only. Leaving both empty keeps email unconfigured. This script creates new stacks; it does not update an existing installation.
3. For a local demo, export `AWS_REGION`, `LEAKLENS_EMAIL_FROM`, and `LEAKLENS_EMAIL_TO` in the backend terminal and use your normal AWS credential profile with the same limited SES permission. Restart the backend. `.env.example` documents variables; it is not loaded automatically. Never put AWS keys in React code or upload them with a CSV.
4. Open **Notifications**, check the displayed recipient, then click **Enable email alerts**. Analyse a file containing previously unseen suspected episodes. Check the notification's email status and the recipient inbox. Existing notifications are not sent retroactively. No test email is sent merely by enabling the setting.
5. Optionally set `LEAKLENS_PUBLIC_URL` on the server to the app's actual URL for links to the saved analysis. On EC2, add it through a systemd service override and restart `leaklens`. Without this variable the email gives navigation instructions. Saved AWS analyses expire after 30 days, so older links can become unavailable.
6. If SES rejects a message, correct verification, region, IAM permission, or sending limits, then use **Retry email**. "Accepted by email service" is not proof of delivery. A network failure can leave the send result uncertain; check SES before retrying to avoid a duplicate. The demo background task is not a durable queue.

Browser notifications are separate from email. They require a user permission gesture and localhost or HTTPS. The basic EC2 template uses HTTP, so browser notifications may be unavailable there until HTTPS is added. The saved in-app inbox still works. See [browser notification permissions](https://developer.mozilla.org/en-US/docs/Web/API/Notification/requestPermission_static).

The template now keeps generated household models under `models/` in S3, outside the `analyses/` expiration rule. Profiles, notification preferences, deduplication records, and findings are retained in DynamoDB. Cleanup instructions for the retained bucket/table still apply.
