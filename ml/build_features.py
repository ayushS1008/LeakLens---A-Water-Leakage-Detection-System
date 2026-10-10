from pathlib import Path
import json
import numpy as np
import pandas as pd

root = Path(__file__).resolve().parents[1]
source = root / "data" / "processed" / "hh01_15min.csv"
output_dir = root / "data" / "features"
output_dir.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(source)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
df = df.sort_values("timestamp").reset_index(drop=True)

# Rolling features require an uninterrupted 15-minute time grid.
spacing = df["timestamp"].diff().iloc[1:]
if not spacing.eq(pd.Timedelta(minutes=15)).all():
    raise SystemExit("The timestamps must form a regular 15-minute grid.")

if len(df) < 100:
    raise SystemExit("Too few intervals to create useful data splits.")

consumption = pd.to_numeric(df["litres_used"], errors="coerce")
usable = df["is_valid"].eq(True) & consumption.ge(0)
consumption = consumption.where(usable)

# Use local time at the START of each consumption interval.
local_start = (
    df["timestamp"] - pd.Timedelta(minutes=15)
).dt.tz_convert("Europe/Berlin")

hour = local_start.dt.hour + local_start.dt.minute / 60
weekday = local_start.dt.dayofweek

features = pd.DataFrame({
    "timestamp": df["timestamp"],
    "litres_used": consumption,
    "previous_litres": consumption.shift(1),
    "mean_last_hour": consumption.rolling(4, min_periods=4).mean(),
    "minimum_last_hour": consumption.rolling(4, min_periods=4).min(),
    "hour_sin": np.sin(2 * np.pi * hour / 24),
    "hour_cos": np.cos(2 * np.pi * hour / 24),
    "weekday_sin": np.sin(2 * np.pi * weekday / 7),
    "weekday_cos": np.cos(2 * np.pi * weekday / 7),
})

feature_columns = [
    column for column in features.columns
    if column != "timestamp"
]

# Keep missing intervals while calculating rolling features.
# Only now remove rows whose model inputs are incomplete.
ready = features.dropna(subset=feature_columns).copy()

# Define splits using the original timeline.
validation_start = df["timestamp"].iloc[int(len(df) * 0.70)]
test_start = df["timestamp"].iloc[int(len(df) * 0.85)]

splits = {
    "train": ready[ready["timestamp"] < validation_start],
    "validation": ready[
        (ready["timestamp"] >= validation_start)
        & (ready["timestamp"] < test_start)
    ],
    "test": ready[ready["timestamp"] >= test_start],
}

for name, data in splits.items():
    if data.empty:
        raise SystemExit(f"The {name} split has no usable rows.")

    destination = output_dir / f"{name}.csv"
    data.to_csv(destination, index=False)
    print(f"{name}: {len(data)} rows")
    print(f"  From: {data['timestamp'].min()}")
    print(f"  To:   {data['timestamp'].max()}")

(output_dir / "feature_columns.json").write_text(
    json.dumps(feature_columns, indent=2),
    encoding="utf-8",
)

print("\nRows excluded due to incomplete inputs:", len(features) - len(ready))
print("Saved files to:", output_dir)
print("\nSample model inputs:")
print(ready.head().to_string(index=False))