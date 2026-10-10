from pathlib import Path
import argparse
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Choose the simulated leak rate and local start hour.
parser = argparse.ArgumentParser()
parser.add_argument(
    "--rate",
    type=float,
    default=1.0,
    help="Artificial leak rate in litres per minute.",
)
parser.add_argument(
    "--hour",
    type=int,
    choices=range(24),
    default=1,
    help="Local start hour, from 0 to 23.",
)
args = parser.parse_args()

if not np.isfinite(args.rate) or args.rate <= 0:
    parser.error("--rate must be a positive, finite number.")

scenario_name = f"{args.rate:g}lpm_{args.hour:02d}h"

root = Path(__file__).resolve().parents[1]
output_dir = root / "data" / "simulation"
output_dir.mkdir(parents=True, exist_ok=True)

# Load the model and its saved settings.
model = joblib.load(root / "models" / "isolation_forest.joblib")
config = json.loads(
    (root / "models" / "detection_config.json").read_text()
)
columns = config["feature_columns"]
threshold = config["anomaly_threshold"]

# Find the validation period.
validation = pd.read_csv(
    root / "data" / "features" / "validation.csv"
)
validation_times = pd.to_datetime(
    validation["timestamp"], utc=True
)
validation_start = validation_times.min()
validation_end = validation_times.max()

# Read processed consumption.
df = pd.read_csv(
    root / "data" / "processed" / "hh01_15min.csv"
)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.sort_values("timestamp")

# Include earlier context for rolling features.
# The final test period is excluded.
df = df[
    (df["timestamp"] >= validation_start - pd.Timedelta(hours=1))
    & (df["timestamp"] <= validation_end)
].reset_index(drop=True)

df["litres_used"] = pd.to_numeric(
    df["litres_used"], errors="coerce"
)
df["litres_used"] = df["litres_used"].where(
    df["is_valid"].eq(True)
)

spacing = df["timestamp"].diff().iloc[1:]
if not spacing.eq(pd.Timedelta(minutes=15)).all():
    raise SystemExit("Expected a continuous 15-minute time grid.")

# Find a complete window at the requested local start hour.
local_start = (
    df["timestamp"] - pd.Timedelta(minutes=15)
).dt.tz_convert("Europe/Berlin")

choices = df.index[
    (df["timestamp"] >= validation_start + pd.Timedelta(days=2))
    & local_start.dt.hour.eq(args.hour)
    & local_start.dt.minute.eq(0)
]

position = None

for i in choices:
    # Require two hours before, four hours during,
    # and four hours after the simulated leak.
    if i >= 8 and i + 32 <= len(df):
        window = df.iloc[i - 8:i + 32]
        if window["litres_used"].notna().all():
            position = i
            break

if position is None:
    raise SystemExit(
        "No complete simulation window found for this start hour."
    )

leak_start = (
    df.loc[position, "timestamp"] - pd.Timedelta(minutes=15)
)
leak_end = leak_start + pd.Timedelta(hours=4)

leak_mask = (
    (df["timestamp"] > leak_start)
    & (df["timestamp"] <= leak_end)
)

# Modify a copy. The original readings remain unchanged.
simulated = df.copy()
simulated.loc[leak_mask, "litres_used"] += args.rate * 15


def analyse(readings):
    """Recalculate training features and apply the alert rule."""
    water = readings["litres_used"]

    local = (
        readings["timestamp"] - pd.Timedelta(minutes=15)
    ).dt.tz_convert("Europe/Berlin")

    hour = local.dt.hour + local.dt.minute / 60
    weekday = local.dt.dayofweek

    features = pd.DataFrame({
        "litres_used": water,
        "previous_litres": water.shift(1),
        "mean_last_hour": water.rolling(
            4, min_periods=4
        ).mean(),
        "minimum_last_hour": water.rolling(
            4, min_periods=4
        ).min(),
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

    # Require four consecutive unusual intervals and
    # positive consumption throughout the last hour.
    alerts = (
        candidates.astype(int)
        .rolling(4, min_periods=4)
        .sum()
        .eq(4)
        & features["minimum_last_hour"].gt(0)
    )

    return scores, candidates, alerts


base_scores, base_candidates, base_alerts = analyse(df)
sim_scores, sim_candidates, sim_alerts = analyse(simulated)

result = pd.DataFrame({
    "timestamp": df["timestamp"],
    "original_litres": df["litres_used"],
    "simulated_litres": simulated["litres_used"],
    "is_simulated_leak": leak_mask,
    "original_score": base_scores,
    "simulated_score": sim_scores,
    "original_alert": base_alerts,
    "simulated_alert": sim_alerts,
})

# Count new alerts during the injection that were absent
# at the same timestamps in the original scenario.
new_alerts = leak_mask & sim_alerts & ~base_alerts

print("Scenario:", scenario_name)
print("Leak rate:", args.rate, "litres/minute")
print("Leak start:", leak_start.tz_convert("Europe/Berlin"))
print("Leak end:", leak_end.tz_convert("Europe/Berlin"))

print(
    "Artificial water added:",
    round(float(leak_mask.sum() * args.rate * 15), 2),
    "litres",
)
print(
    "Original candidate intervals during window:",
    int((base_candidates & leak_mask).sum()),
)
print(
    "Simulated candidate intervals during window:",
    int((sim_candidates & leak_mask).sum()),
)
print(
    "New alert detected during injection:",
    bool(new_alerts.any()),
)

if new_alerts.any():
    first_alert = df.loc[new_alerts, "timestamp"].iloc[0]
    delay = (first_alert - leak_start).total_seconds() / 60
    print("First new alert after:", int(delay), "minutes")
else:
    print("No new alert detected during this injection.")

# Save validation results only.
result = result[
    result["timestamp"] >= validation_start
].copy()

csv_path = output_dir / f"leak_simulation_{scenario_name}.csv"
result.to_csv(csv_path, index=False)

# Plot the surrounding ten-hour window.
view = result[
    (result["timestamp"] > leak_start - pd.Timedelta(hours=2))
    & (result["timestamp"] <= leak_end + pd.Timedelta(hours=4))
].copy()

times = view["timestamp"].dt.tz_convert("Europe/Berlin")

fig, ax = plt.subplots(figsize=(12, 5))

ax.plot(
    times,
    view["original_litres"],
    label="Original readings",
)
ax.plot(
    times,
    view["simulated_litres"],
    label="With artificial leak",
)

ax.axvspan(
    leak_start.tz_convert("Europe/Berlin"),
    leak_end.tz_convert("Europe/Berlin"),
    alpha=0.15,
    color="orange",
    label="Artificial leak period",
)

marked = view["simulated_alert"]
ax.scatter(
    times[marked],
    view.loc[marked, "simulated_litres"],
    color="red",
    label="Simulated alert intervals",
    zorder=3,
)

ax.set_ylabel("Litres per 15-minute interval")
ax.set_xlabel("Time — Europe/Berlin")
ax.set_title(
    f"LeakLens simulation: {args.rate:g} L/min, "
    f"starting at {args.hour:02d}:00"
)
ax.legend()
ax.grid(alpha=0.3)

fig.autofmt_xdate()
fig.tight_layout()

png_path = output_dir / f"leak_simulation_{scenario_name}.png"
fig.savefig(png_path, dpi=150)
plt.close(fig)

print("\nCSV saved:", csv_path)
print("Chart saved:", png_path)