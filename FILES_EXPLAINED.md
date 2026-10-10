# Why these files are needed

| File | Purpose |
|---|---|
| backend/main.py | Exposes analysis, ticket creation/update, and follow-up endpoints. Restores a saved analysis after a browser refresh. Serves the built website. |
| backend/storage.py | Saves analyses and tickets in SQLite locally, or S3/DynamoDB on AWS. Prevents duplicate tickets and conflicting updates. |
| backend/workflow.py | Defines ticket statuses and compares complete before/after repair windows without treating missing data as success. |
| frontend/src/App.jsx | Coordinates separate Overview, Alerts, Maintenance, and Day details pages. Keeps the analysis across navigation and restores it after refresh. Opens the correct ticket after creation. |
| frontend/src/App.css | Styles navigation, summary cards, instant chart tooltips, daily reports, ticket forms, and mobile layouts. |
| frontend/src/Maintenance.jsx | Displays saved tickets, investigation/repair forms, follow-up uploads, results, and activity history. |
| frontend/src/api.js | Provides one shared function for frontend API calls and readable errors. |
| frontend/src/navigation.js | Provides bookmarkable page URLs and browser Back/Forward navigation without adding a routing dependency. |
| frontend/src/analysis.js | Computes daily totals, data coverage, peak consumption, and episodes overlapping the selected UTC date. |
| frontend/src/ConsumptionChart.jsx | Shows consumption with instant pointer, touch, and keyboard inspection instead of delayed browser tooltips. |
| frontend/src/DayDetails.jsx | Lets you enter a date and read its summary, data quality, related alerts, and chart at the end. |
| requirements.txt | Records all installed Python dependencies for local development and ML scripts, including the AWS SDK. |
| requirements-runtime.txt | Lists pinned packages needed by the deployed API/model, avoiding unnecessary training/plotting tools. |
| tests/test_workflow.py | Checks persistence, duplicate prevention, revision conflicts, repair timing, incomplete data, and AWS adapter requests using stubs. |
| ml/build_demo.py | Creates an explicitly synthetic leak/repair demo using the frozen model and attributed household data. |
| data/demo/leak_before_repair.csv | Sample upload with a synthetic 1 L/min added flow during the 24-hour comparison window. |
| data/demo/followup_after_repair.csv | Sample follow-up with the added flow removed, plus preceding context for model features. |
| data/demo/demo_instructions.json | Gives the exact repair time and clearly identifies the example as simulated. |
| deploy/build_bundle.py | Packages only the app, model, runtime requirements, and notices for AWS; excludes credentials and raw/private data. |
| build/leaklens-deploy.zip | The generated deployment package to upload to AWS CloudShell. |
| deploy/cloudformation.json | Defines the EC2 instance, networking, private S3 bucket, DynamoDB table, and limited instance-role permissions. |
| deploy/deploy_aws.sh | Runs in signed-in AWS CloudShell to upload the artifact, create the stack, and wait for the app health check. |
| deploy/AWS_STEPS.md | Explains account setup, upload/deploy steps, live verification, troubleshooting, and cleanup. |
| .env.example | Documents storage configuration variables. Contains no credentials and is not loaded automatically. |
| .gitignore | Keeps the virtual environment, raw data, private ticket database, keys, node_modules, and build artifacts out of Git. |
| README.md | Explains the problem, local setup, demo flow, evaluation, limitations, and how to run checks. |
| CREDITS.md | Attributes the dataset, lists third-party libraries and licences, and discloses AI assistance. |
| THIRD_PARTY_NOTICES.txt | Preserves installed dependency licence/notice texts and bundled frontend package notices. |
| LICENSE | Provides an MIT licence for project code; dataset-derived CSVs retain their separate CC BY 4.0 terms. |
| submission/WRITEUP.md | Provides a short submission draft with team, repository, video, and actual AWS status fields to complete. |
| submission/DEMO_SCRIPT.md | Gives a 2:45 recording outline that shows every important feature and genuine AWS usage. |
| submission/CHECKLIST.md | Tracks the required public repo, video, writeup, credits, event-window eligibility, and deadline. |
| FILES_EXPLAINED.md | This guide: connects each file to its role in the project. |

Generated at runtime: `data/app/leaklens.sqlite3` stores local analyses and tickets. It is intentionally excluded from Git. On AWS, analysis objects go to private S3 and tickets go to DynamoDB instead.

Existing `backend/detector.py`, model/configuration, preprocessing scripts, and reserved evaluation results were not retrained or retuned by this finishing work.

## Added for household profiles and investigation tools

- `backend/households.py`: validates household identity, trains and saves a separate baseline model per new household, and builds factual alert explanations. This prevents applying hh-01's model to unrelated homes.
- `backend/notifications.py`: groups new episodes into a persistent inbox, deduplicates repeated uploads, and handles optional AWS SES email status and retries.
- `frontend/src/Households.jsx`: provides profile creation and selection, with baseline requirements explained in the interface.
- `frontend/src/AlertExplanation.jsx`: displays the measured conditions behind an alert in Alerts, Day details, and Maintenance.
- `frontend/src/Notifications.jsx`: provides the inbox, mark-as-read, delivery status, and opt-in controls.
- `frontend/src/useNotifications.js`: refreshes the inbox and requests browser permission only when the user enables notifications; avoids repeating previously shown browser alerts.
- `frontend/src/reports.js`: creates CSV exports and print-ready HTML reports that can be saved as PDF. Escapes user text and protects spreadsheet exports against formulas in free-text notes.
- `frontend/src/ReportActions.jsx`: shares the report buttons between Overview, Day details, and tickets.
- `tests/test_features.py`: checks household isolation, persisted model loading, factual explanations, independent user findings, notification deduplication, and email acceptance/failure using stubs.

Updated `backend/storage.py` also saves household artifacts/profiles and inbox settings; `backend/workflow.py` records investigation outcomes; `backend/main.py` connects their APIs. `Maintenance.jsx` includes the user finding form. `App.jsx` keeps household-specific analyses and routes notification links. `App.css` applies the visual polish. Deployment/configuration documents explain optional SES setup and retained model storage. These updates do not retrain or retune the existing hh-01 model.

## Local AWS connection

- `deploy/run_aws_local.py` starts the website with explicit AWS settings and checks
  the chosen account/table, preventing accidental local mode after changing terminals.
- `deploy/AWS_LOCAL.md` explains AWS login, configuration, live verification and cleanup.
- `.aws/leaklens-local.json` is the private machine configuration; it is ignored by Git.
- `.aws/local-app-policy.json` records the narrow permissions applied to the app IAM user.
- `.aws/console-login.txt` supplies the temporary first console login, never for publishing.
- `.aws/aws-verification.json` records private results of live AWS tests.

- `deploy/AWS_VERIFICATION.md` records what was actually checked against live AWS and distinguishes cloud integration from optional website hosting.
