# LeakLens

[GitHub repository](https://github.com/ayushS1008/LeakLens---A-Water-Leakage-Detection-System)

Water leaks can continue unnoticed because a meter total does not explain whether use is ordinary or persistent. LeakLens analyses one household's 15-minute water readings, flags persistent unusual usage, and connects an alert to an investigation, a reported repair, and a follow-up comparison.

Track: **Heat and Water**. This is a hackathon prototype trained on household hh-01, not a validated leak diagnosis service.

A beginner guide to each file is in [FILES_EXPLAINED.md](FILES_EXPLAINED.md).

## What works

- CSV validation, missing-data handling, chronological train/validation/test splits, and an Isolation Forest.
- Dashboard with daily consumption charts, unknown intervals, and suspected alert episodes.
- Persistent maintenance tickets with duplicate prevention, activity history, and revision checks.
- Report a repair time, then upload follow-up readings to compare complete 24-hour windows before and after repair.
- Local SQLite storage, or AWS S3 analysis storage and DynamoDB ticket storage. An EC2 deployment template is provided.

## Run locally

Use Python 3.12 or 3.13 and a Node.js version supported by Vite. The saved model uses scikit-learn 1.9.1; keep the pinned runtime dependencies.

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open the Local URL shown by Vite. The development proxy forwards `/api` requests to port 8000. API documentation is at `http://127.0.0.1:8000/docs`.

For a single-server local preview, build the frontend, restart the backend, and open port 8000:

```bash
cd frontend
npm run build
```

## Reproduce the data pipeline

Download hh-01.zip from [Smart Meter Water Consumption Measurements](https://doi.org/10.5281/zenodo.7506076). Extract the CSV to `data/hh-01/smartmeter.csv`. Data is CC BY 4.0; see CREDITS.md.

Run, in this order: `ml/check_data.py`, `ml/prepare_data.py`, `ml/build_features.py`, `ml/train_model.py`, and `ml/set_threshold.py`. The selected threshold is the 98th percentile of validation scores. Run `ml/evaluate_test.py` once on the reserved test period with frozen settings. These scripts read paths relative to this repository.

The existing `data/evaluation/test_report.json` records the completed evaluation. Do not tune the model using test results.

## Demonstrate a synthetic leak and repair

Run `python ml/build_demo.py` after preparing the original dataset, or use the included `data/demo` files:

1. Upload `data/demo/leak_before_repair.csv`, and analyse it.
2. Click **Create ticket** on an alert; choose **Start investigating** in Maintenance.
3. Copy `repair_time_for_dashboard` from `data/demo/demo_instructions.json` into the repair-time input. The input uses UTC; enter a short note explaining that this is a synthetic repair demonstration.
4. Click **Report repair**.
5. Upload `data/demo/followup_after_repair.csv` in the ticket and click **Check follow-up readings**.
6. Refresh the page to demonstrate that the ticket and follow-up result persist.

The demo adds 1 L/min for 24 hours and removes the added flow at the reported repair. It is an illustrative simulation, not a verified real repair or an additional held-out performance claim.

## Evaluation and limits

The fixed detector detected all four selected constant-rate injected test scenarios: 0.25, 0.5, 1, and 2 L/min. Delays were 105, 105, 75, and 75 minutes. The comparison continuous-flow rule detected the same scenarios in 60, 60, 30, and 30 minutes.

There were 2 ML alert episodes and 16 simple-rule episodes on original test readings. Original readings have no confirmed leak labels, so these counts are background alerts, not known false alarms. Four scenarios across two selected windows do not establish real-world accuracy.

Follow-up improvement means alerts were present in a complete 24-hour pre-repair window and absent in the complete 24-hour post-repair window. It is not proof that a leak existed or was repaired. Changes in occupancy and ordinary use can affect consumption; the app makes no measured water-saving claim.

The prototype has no user authentication or household ownership checks. Deploy it for a short demonstration using sample data; a production version needs access controls and HTTPS. S3 analysis objects in the demo deployment expire after 30 days, so later follow-up checks require the source analysis to remain available.

## AWS and submission

Live integration with S3, DynamoDB and SES has been verified using the limited app IAM user, including persistence after restart and recipient-confirmed email delivery. The website currently runs on the demo laptop. See [deploy/AWS_VERIFICATION.md](deploy/AWS_VERIFICATION.md) for evidence and [deploy/AWS_LOCAL.md](deploy/AWS_LOCAL.md) to run it. `deploy/AWS_STEPS.md` describes optional EC2 hosting, which has not been deployed.

See `submission/WRITEUP.md`, `submission/DEMO_SCRIPT.md`, and `submission/CHECKLIST.md`. Fill in team-specific fields, publish a public repository, and record a YouTube video strictly under three minutes.

## Checks

```bash
python -m unittest discover -s tests -v
```

In the frontend directory, run `npm run lint` and `npm run build`. AWS adapter unit tests use SDK stubs. The separate live AWS smoke test and restart checks are recorded in [deploy/AWS_VERIFICATION.md](deploy/AWS_VERIFICATION.md).

## Credits and AI disclosure

See CREDITS.md and THIRD_PARTY_NOTICES.txt. Project code is MIT licensed; the dataset and included derived demo CSVs remain under CC BY 4.0. Model construction uses that attributed dataset.

AI assistance used: **OpenAI ChatGPT / Codex** for planning, code generation, debugging, and documentation. Add any other tools your team used before submitting.

## Website pages

Overview keeps the upload, summary cards, and daily chart together. Alerts has the episode list and ticket actions. Creating a ticket opens that specific ticket on Maintenance; an existing record uses Open ticket. Day details accepts a UTC date and shows the day's summary, coverage, related alerts, and a chart at the end. All pages support browser Back/Forward through hash URLs (for example `/#/alerts`), so they work with both Vite and the built website on port 8000.

Chart details appear immediately when you move across the plot, including unknown intervals; you can also tap on mobile or focus the chart and use arrow keys. The last analysis is restored from server storage after a refresh in the same browser tab. Only its identifier is kept in session storage. Tickets remain saved independently of the selected analysis.

## Household profiles, findings, notifications, and reports

Select a household in the header. **Households** lets you add a name, ID, timezone, and a processed baseline CSV containing the same `household_id` on every row. A new profile needs at least 14 days and 80% complete feature windows; its earlier 70% trains an independent Isolation Forest and its later 30% calibrates the threshold. Models are saved separately. This minimum is a prototype requirement, not evidence of detection accuracy. Validate new profiles on future labelled readings before relying on them. The built-in hh-01 model and threshold remain unchanged.

**Alerts → Why was this flagged?** shows the readings that satisfied the rule: four unusual scores, positive use in each recent interval, and litres in the trigger hour. These are observed conditions, not causal explanations or a guarantee of a leak. Uploading baseline dates shows an overlap notice.

**Maintenance → Human review** records a confirmed leak, normal activity, or undetermined outcome with a required note. Findings are explicitly user reported, remain in ticket history, and do not automatically change the model or its predictions. Repair reporting and follow-up comparison remain separate.

**Notifications** has a saved inbox across all households, grouped notifications, mark-as-read, browser opt-in, email opt-in, and email retry/status. Re-uploaded episodes with the same household, model and first-alert time are deduplicated. Browser notifications require permission and an open tab on localhost or HTTPS; operating-system settings also apply. These features respond to uploaded files, not live meters. Email uses AWS SES and a fixed server-configured recipient, with details in `deploy/AWS_STEPS.md`. Accepted means SES accepted the request, not confirmed inbox delivery. The prototype uses background tasks, not a durable email queue; a server interruption during sending may require operator investigation. Concurrent overlapping uploads can produce overlapping notification groups. Enable email only on a trusted or access-restricted demo installation.

**Download CSV** exports analysed readings (or one selected day) and ticket history. **Print / save PDF** opens a clean report with summaries, alert evidence, and the selected day's chart; choose Save as PDF in the browser print dialog. Ticket reports include user findings and repair comparisons. Exports keep missing values blank, escape free text, and retain the prototype's limitations.

This is a shared demo installation, not a multi-user service with household access controls. Profiles, settings and inbox are shared by people using the same server. Local data stays in SQLite; AWS mode stores generated models under `models/` in S3 and profiles/findings/inbox/settings in DynamoDB. The optional CloudFormation deployment applies 30-day expiry only to `analyses/`; household models are retained. The current manually created bucket has no lifecycle expiry. Live AWS verification is recorded in [deploy/AWS_VERIFICATION.md](deploy/AWS_VERIFICATION.md).

## Local website connected to AWS

Use `.venv/bin/python deploy/run_aws_local.py` from the project root after configuring
your own local `.aws/leaklens-local.json` and browser-login profile. This keeps the
website on your Mac and uses real S3, DynamoDB and optional SES. See
[deploy/AWS_LOCAL.md](deploy/AWS_LOCAL.md) for why each file is needed, credential
refresh, verification, costs, and cleanup. The EC2 deployment is a separate option.
