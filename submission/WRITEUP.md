# LeakLens — From unusual water use to a tracked repair

Track: Heat and Water

Team name: **[fill in]**
Public repository: https://github.com/ayushS1008/LeakLens---A-Water-Leakage-Detection-System
YouTube demo (under three minutes): **[fill in]**

## Problem

A rising meter total cannot tell a household whether consumption is ordinary or caused by persistent unwanted flow. Without an actionable alert and a way to track follow-up, a suspected leak can remain unresolved.

## What we built

LeakLens accepts a household's processed 15-minute readings, shows consumption and data gaps, and uses an Isolation Forest plus persistence criteria to flag suspected leak episodes. Users create a maintenance ticket, record investigation and a reported repair time, then upload follow-up readings. The app compares complete 24-hour windows before and after repair and distinguishes improvement, persistent alerts, inconclusive results, and insufficient data.

## AI/ML and evaluation

We trained on earlier household hh-01 readings, selected a threshold using a later validation period, and froze it for the reserved test period. The detector found four selected synthetic constant-rate leak scenarios with delays of 75–105 minutes. The simple continuous-flow rule found them faster, but produced 16 background episodes versus 2 for the ML detector on original test readings. Those episodes are not verified false alarms because real leak labels are absent. Four injected scenarios across two windows are a limited evaluation.

The demo adds an explicitly artificial 1 L/min flow and removes it to illustrate a repair. Neither simulated evaluation nor the follow-up comparison establishes real-world accuracy, proves a repair, or measures water saved.

## Where AWS fits

**AWS integration status: live S3, DynamoDB and SES verified on 10 October 2026, including persistence after restart and recipient-confirmed email delivery. The website runs locally on the demo laptop; EC2/public hosting has not been deployed.**

The running app uses S3 for compressed analyses and generated household models, DynamoDB for tickets, follow-up reports, household profiles, findings and notification records, and SES for opted-in email alerts. A limited IAM user signs in through AWS CLI using temporary credentials; no permanent access keys are embedded. Real writes and reads were tested, and records remained accessible after restarting the local backend. The optional EC2 template uses an instance role, but that hosting path has not been deployed. Show the actual cloud records and received alert in the demo video; see deploy/AWS_VERIFICATION.md.

## Credits and AI disclosure

Data: Wilhelm, Kasbauer, Jakob, Elser, and Ahrens, *Smart Meter Water Consumption Measurements*, version 1.0, https://doi.org/10.5281/zenodo.7506076 , CC BY 4.0. We derived 15-minute consumption/features and modified demo readings to add/remove synthetic flow.

Libraries: React, Vite, FastAPI, pandas, NumPy, scikit-learn, joblib, Matplotlib, and Boto3. See CREDITS.md and THIRD_PARTY_NOTICES.txt for licences and transitive dependencies.

AI tools used: OpenAI ChatGPT / Codex for planning, coding, debugging, tests, and documentation. **Add other tools actually used by the team.**

Build period: **[record the actual event opening, your development dates, and submission deadline; submit only work eligible under the event rules]**.
