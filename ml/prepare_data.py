from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parents[1]
source = root / "data" / "hh-01" / "smartmeter.csv"
output_dir = root / "data" / "processed"
output_dir.mkdir(parents=True, exist_ok=True)

# Load and sort the original readings.
df = pd.read_csv(source, usecols=["time", "total_m3"])
df["time"] = pd.to_datetime(df["time"], utc=True, errors="raise")
df["total_m3"] = pd.to_numeric(df["total_m3"], errors="raise")
df = df.sort_values("time").reset_index(drop=True)

if df["time"].duplicated().any():
    raise SystemExit("Duplicate timestamps found. Resolve them first.")

# Identify recording gaps and decreases in the cumulative meter.
previous_time = df["time"].shift()
gap_seconds = df["time"].diff().dt.total_seconds()
meter_change = df["total_m3"].diff()

# Conservative starting rule:
# gaps over 60 seconds make the affected intervals unreliable.
problem = (gap_seconds > 60) | (meter_change < -0.000001)

# Keep the last available meter reading at each 15-minute boundary.
df["sample_time"] = df["time"]
df = df.set_index("time")

readings = df.resample(
    "15min", closed="right", label="right"
).agg({
    "total_m3": "last",
    "sample_time": "last",
})

# Difference between cumulative readings, converted from m³ to litres.
litres = readings["total_m3"].diff().mul(1000).round(6)

# Both boundary readings must be reasonably close to their boundaries.
age_seconds = (
    readings.index.to_series() - readings["sample_time"]
).dt.total_seconds()

fresh = age_seconds.between(0, 60)
valid = fresh & fresh.shift(fill_value=False) & litres.notna()

# Mark every interval touched by a gap or meter decrease.
for position in problem[problem].index:
    start = previous_time.loc[position].ceil("15min")
    end = df.index[position].ceil("15min")
    valid.loc[start:end] = False

valid = valid & (litres >= -0.000001)

result = pd.DataFrame({
    "timestamp": readings.index,
    "household_id": "hh-01",
    "litres_used": litres.where(valid).clip(lower=0).to_numpy(),
    "is_valid": valid.to_numpy(),
})

output = output_dir / "hh01_15min.csv"
result.to_csv(output, index=False)

print("Saved:", output)
print("Total intervals:", len(result))
print("Valid intervals:", result["is_valid"].sum())
print("Unknown intervals:", (~result["is_valid"]).sum())
print("\nFirst valid intervals:")
print(result[result["is_valid"]].head().to_string(index=False))