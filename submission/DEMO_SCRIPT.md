# Demo video — target 2 minutes 45 seconds

Record the completed app and actual AWS account. Say clearly that the leak/repair example is simulated. Do not show account credentials or private data.

| Time | Show | Say |
|---|---|---|
| 0:00–0:20 | Dashboard | "LeakLens helps turn persistent unusual water use into an investigation and tracked follow-up. A meter total alone does not explain the pattern." |
| 0:20–0:55 | Upload leak_before_repair.csv; chart and alert table | "This demonstration adds a synthetic 1 litre per minute flow to public household readings. Our model and persistence check flag episodes for review; an alert is not a confirmed leak." |
| 0:55–1:35 | Create ticket; start investigating; report the documented repair time | "We turn an episode into a saved ticket and record a reported repair. Here the added flow is removed to represent a repair." |
| 1:35–2:05 | Upload followup_after_repair.csv; before/after result; refresh | "The app checks complete 24-hour windows. It reports improvement if alerts disappear, and refuses to pass incomplete data. The ticket survives refresh." |
| 2:05–2:30 | Deployed app, S3 object, DynamoDB ticket and EC2 instance | "EC2 runs our model service and dashboard. This S3 object stores the analysis, and this DynamoDB record stores the actual ticket and follow-up result." |
| 2:30–2:45 | Evaluation report and repository | "On four selected injected test scenarios, detection took 75–105 minutes. ML produced fewer background episodes than a simple flow rule, with slower detection. This is a single-household prototype; real leak accuracy and water savings are not established." |

Upload to YouTube as public or unlisted. Confirm the video is **strictly under 3:00**, and test the link in a signed-out browser. Anything not shown in the video may not count under the supplied judging rules.
