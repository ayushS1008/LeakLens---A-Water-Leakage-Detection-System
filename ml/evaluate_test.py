from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[1]
output_dir = root / "data" / "evaluation"
output_dir.mkdir(parents=True, exist_ok=True)

model = joblib.load(root / "models" / "isolation_forest.joblib")
config = json.loads(
    (root / "models" / "detection_config.json").read_text()
)
columns = config["feature_columns"]
threshold = float(config["anomaly_threshold"])

# Identify the reserved test period.
test = pd.read_csv(root / "data" / "features" / "test.csv")
test_times = pd.to_datetime(test["timestamp"], utc=True)
test_start = test_times.min()
test_end = test_times.max()

df = pd.read_csv(root / "data" / "processed" / "hh01_15min.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.sort_values("timestamp")

# Earlier readings supply context; reported results cover only test time.
df = df[
    (df["timestamp"] >= test_start - pd.Timedelta(hours=1))
    & (df["timestamp"] <= test_end)
].reset_index(drop=True)

df["litres_used"] = pd.to_numeric(
    df["litres_used"], errors="coerce"
)
df["litres_used"] = df["litres_used"].where(
    df["is_valid"].eq(True)
)

spacing = df["timestamp"].diff().iloc[1:]
if not spacing.eq(pd.Timedelta(minutes=15)).all():
    raise SystemExit("Expected a continuous 15-minute grid.")


def analyse(readings):
    water = readings["litres_used"]
    local = (
        readings["timestamp"] - pd.Timedelta(minutes=15)
    ).dt.tz_convert("Europe/Berlin")

    hour = local.dt.hour + local.dt.minute / 60
    weekday = local.dt.dayofweek

    features = pd.DataFrame({
        "litres_used": water,
        "previous_litres": water.shift(1),
        "mean_last_hour": water.rolling(4, min_periods=4).mean(),
        "minimum_last_hour": water.rolling(4, min_periods=4).min(),
        "hour_sin": np.sin(2 * np.pi * hour / 24),
        "hour_cos": np.cos(2 * np.pi * hour / 24),
        "weekday_sin": np.sin(2 * np.pi * weekday / 7),
        "weekday_cos": np.cos(2 * np.pi * weekday / 7),
    })

    usable = features[columns].notna().all(axis=1)
    scores = pd.Series(np.nan, index=readings.index)
    scores.loc[usable] = -model.score_samples(
        features.loc[usable, columns]
    )

    candidates = scores > threshold
    continuous_flow = features["minimum_last_hour"].gt(0)

    ml_alerts = (
        candidates.astype(int)
        .rolling(4, min_periods=4)
        .sum()
        .eq(4)
        & continuous_flow
    )

    # Simple comparison rule; no ML scores are used.
    rule_alerts = continuous_flow

    return ml_alerts, rule_alerts


def count_episodes(alerts):
    return int(
        (alerts & ~alerts.shift(fill_value=False)).sum()
    )


def detection_result(alerts, original_alerts, mask, start):
    new_alerts = mask & alerts & ~original_alerts

    if not new_alerts.any():
        return False, None

    first_alert = df.loc[new_alerts, "timestamp"].iloc[0]
    delay = (first_alert - start).total_seconds() / 60
    return True, float(delay)


original_ml, original_rule = analyse(df)
test_mask = df["timestamp"] >= test_start

ml_background = count_episodes(original_ml.loc[test_mask])
rule_background = count_episodes(original_rule.loc[test_mask])

local_start = (
    df["timestamp"] - pd.Timedelta(minutes=15)
).dt.tz_convert("Europe/Berlin")

rows = []

for rate, start_hour in [(0.25, 1), (0.5, 1), (1.0, 12), (2.0, 12)]:
    choices = df.index[
        (df["timestamp"] >= test_start + pd.Timedelta(days=2))
        & local_start.dt.hour.eq(start_hour)
        & local_start.dt.minute.eq(0)
    ]

    position = None

    for i in choices:
        if i >= 8 and i + 32 <= len(df):
            window = df.iloc[i - 8:i + 32]
            if window["litres_used"].notna().all():
                position = i
                break

    if position is None:
        raise SystemExit(
            f"No complete test window for start hour {start_hour}."
        )

    leak_start = (
        df.loc[position, "timestamp"] - pd.Timedelta(minutes=15)
    )
    leak_end = leak_start + pd.Timedelta(hours=4)

    mask = (
        (df["timestamp"] > leak_start)
        & (df["timestamp"] <= leak_end)
    )

    simulated = df.copy()
    simulated.loc[mask, "litres_used"] += rate * 15

    simulated_ml, simulated_rule = analyse(simulated)

    ml_detected, ml_delay = detection_result(
        simulated_ml, original_ml, mask, leak_start
    )
    rule_detected, rule_delay = detection_result(
        simulated_rule, original_rule, mask, leak_start
    )

    rows.append({
        "rate_lpm": rate,
        "start_hour": start_hour,
        "leak_start": str(leak_start),
        "added_litres": float(mask.sum() * rate * 15),
        "ml_new_alert": ml_detected,
        "ml_delay_minutes": ml_delay,
        "rule_new_alert": rule_detected,
        "rule_delay_minutes": rule_delay,
    })

results = pd.DataFrame(rows)
csv_path = output_dir / "test_scenario_results.csv"
results.to_csv(csv_path, index=False)

report = {
    "test_start": str(test_start),
    "test_end": str(test_end),
    "fixed_anomaly_threshold": threshold,
    "original_ml_alert_episodes": ml_background,
    "original_rule_alert_episodes": rule_background,
    "scenarios": rows,
    "limitations": [
        "Original readings have no verified leak labels.",
        "Injected leaks are constant-rate artificial scenarios.",
        "Four scenarios across two selected windows are a limited evaluation.",
        "Background alerts are not confirmed false alarms.",
    ],
}

json_path = output_dir / "test_report.json"
json_path.write_text(
    json.dumps(report, indent=2, allow_nan=False),
    encoding="utf-8",
)

print("Test period:", test_start, "to", test_end)
print("Fixed threshold:", round(threshold, 6))
print("\nAlert episodes on original test readings:")
print("ML detector:", ml_background)
print("Simple continuous-flow rule:", rule_background)

print("\nInjected test scenarios:")
print(
    results[
        [
            "rate_lpm",
            "start_hour",
            "ml_new_alert",
            "ml_delay_minutes",
            "rule_new_alert",
            "rule_delay_minutes",
        ]
    ].to_string(index=False)
)

print("\nCSV saved:", csv_path)
print("Report saved:", json_path)
print("Model and settings were not changed.")