from pathlib import Path
import json
import pandas as pd

root = Path(__file__).resolve().parents[1]
simulation_dir = root / "data" / "simulation"

config = json.loads(
    (root / "models" / "detection_config.json").read_text()
)

paths = sorted(
    simulation_dir.glob("leak_simulation_*lpm_*h.csv")
)

if not paths:
    raise SystemExit("No named simulation CSV files found.")

frames = {}

for path in paths:
    frame = pd.read_csv(path)
    frame["timestamp"] = pd.to_datetime(
        frame["timestamp"], utc=True
    )
    frame = frame.sort_values("timestamp").reset_index(drop=True)

    spacing = frame["timestamp"].diff().iloc[1:]
    if not spacing.eq(pd.Timedelta(minutes=15)).all():
        raise SystemExit(f"Irregular time grid in {path.name}")

    frames[path.stem] = frame

# These experiments should share the same original validation data.
reference = next(iter(frames.values()))

for name, frame in frames.items():
    if (
        not frame["timestamp"].equals(reference["timestamp"])
        or not frame["original_score"].equals(
            reference["original_score"]
        )
        or not frame["original_litres"].equals(
            reference["original_litres"]
        )
    ):
        raise SystemExit(
            "Simulation files use different original data or scores. "
            "Rerun them with the same model before comparing."
        )

original_scores = reference["original_score"].dropna()

thresholds = {
    "current": float(config["anomaly_threshold"]),
    "98th percentile": float(original_scores.quantile(0.98)),
    "97th percentile": float(original_scores.quantile(0.97)),
    "95th percentile": float(original_scores.quantile(0.95)),
}


def make_alerts(scores, consumption, threshold):
    candidates = scores > threshold

    consecutive = (
        candidates.astype(int)
        .rolling(4, min_periods=4)
        .sum()
        .eq(4)
    )

    continuous_flow = (
        consumption.rolling(4, min_periods=4).min().gt(0)
    )

    return consecutive & continuous_flow


def count_episodes(alerts):
    # Consecutive alert intervals belong to one episode.
    starts = alerts & ~alerts.shift(fill_value=False)
    return int(starts.sum())


rows = []

for setting, threshold in thresholds.items():
    original_alerts = make_alerts(
        reference["original_score"],
        reference["original_litres"],
        threshold,
    )
    background_episodes = count_episodes(original_alerts)

    for scenario, frame in frames.items():
        leak = frame["is_simulated_leak"].eq(True)

        if not leak.any():
            raise SystemExit(f"No injection labels in {scenario}")

        simulated_alerts = make_alerts(
            frame["simulated_score"],
            frame["simulated_litres"],
            threshold,
        )

        # Identify alerts newly introduced during the injection.
        new_alerts = leak & simulated_alerts & ~original_alerts
        detected = bool(new_alerts.any())
        delay = None

        if detected:
            leak_start = (
                frame.loc[leak, "timestamp"].iloc[0]
                - pd.Timedelta(minutes=15)
            )
            first_alert = frame.loc[
                new_alerts, "timestamp"
            ].iloc[0]
            delay = (
                first_alert - leak_start
            ).total_seconds() / 60

        rows.append({
            "setting": setting,
            "threshold": round(threshold, 6),
            "scenario": scenario.replace("leak_simulation_", ""),
            "detected": detected,
            "delay_minutes": delay,
            "original_alert_episodes": background_episodes,
        })

report = pd.DataFrame(rows)

output = simulation_dir / "threshold_comparison.csv"
report.to_csv(output, index=False)

print(report.to_string(index=False))
print("\nSaved:", output)
print(
    "\nOriginal alert episodes are background alerts, "
    "not confirmed false alarms."
)
print("The saved model and detection settings were not changed.")