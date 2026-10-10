from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest

root = Path(__file__).resolve().parents[1]
feature_dir = root / "data" / "features"
model_dir = root / "models"
model_dir.mkdir(parents=True, exist_ok=True)

columns = json.loads(
    (feature_dir / "feature_columns.json").read_text()
)

train = pd.read_csv(feature_dir / "train.csv")
validation = pd.read_csv(feature_dir / "validation.csv")

X_train = train[columns]
X_validation = validation[columns]

if not np.isfinite(X_train.to_numpy()).all():
    raise SystemExit("Training inputs contain missing or infinite values.")

if not np.isfinite(X_validation.to_numpy()).all():
    raise SystemExit("Validation inputs contain missing or infinite values.")

print("Training Isolation Forest...")

model = IsolationForest(
    n_estimators=200,
    max_samples=min(1024, len(train)),
    contamination="auto",
    random_state=42,
    n_jobs=-1,
)

model.fit(X_train)

# Negate the score so higher values mean more unusual readings.
validation["anomaly_score"] = -model.score_samples(X_validation)

# Initial investigation threshold: upper 1% of validation scores.
# This is a starting setting, not a measured leak probability.
threshold = float(validation["anomaly_score"].quantile(0.99))

validation["is_candidate"] = (
    validation["anomaly_score"] > threshold
)

joblib.dump(model, model_dir / "isolation_forest.joblib")

settings = {
    "feature_columns": columns,
    "anomaly_threshold": threshold,
    "threshold_method": "99th percentile of validation anomaly scores",
    "timezone": "Europe/Berlin",
    "interval_minutes": 15,
    "sklearn_version": sklearn.__version__,
    "training_rows": len(train),
    "validation_rows": len(validation),
    "random_state": 42,
}

(model_dir / "detection_config.json").write_text(
    json.dumps(settings, indent=2),
    encoding="utf-8",
)

validation.to_csv(
    feature_dir / "validation_scores.csv",
    index=False,
)

print("\nTraining complete.")
print("Anomaly threshold:", round(threshold, 4))
print("Validation candidates:", int(validation["is_candidate"].sum()))

print("\nTen most unusual validation readings:")
print(
    validation.nlargest(10, "anomaly_score")[
        [
            "timestamp",
            "litres_used",
            "minimum_last_hour",
            "anomaly_score",
            "is_candidate",
        ]
    ].to_string(index=False)
)

print("\nModel saved in:", model_dir)