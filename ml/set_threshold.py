from pathlib import Path
import json
import pandas as pd

root = Path(__file__).resolve().parents[1]
config_path = root / "models" / "detection_config.json"

config = json.loads(config_path.read_text())

validation = pd.read_csv(
    root / "data" / "features" / "validation_scores.csv"
)

scores = validation["anomaly_score"].dropna()

if scores.empty:
    raise SystemExit("No validation scores found.")

old_threshold = config["anomaly_threshold"]
new_threshold = float(scores.quantile(0.98))

# Preserve the initial setting for reference.
config.setdefault("initial_anomaly_threshold", old_threshold)

config["anomaly_threshold"] = new_threshold
config["threshold_method"] = (
    "98th percentile of validation anomaly scores"
)

config_path.write_text(
    json.dumps(config, indent=2),
    encoding="utf-8",
)

print("Previous threshold:", round(old_threshold, 6))
print("Updated threshold:", round(new_threshold, 6))
print("Configuration saved:", config_path)