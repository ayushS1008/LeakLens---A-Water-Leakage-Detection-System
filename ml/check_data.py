from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parents[1]
path = root / "data" / "hh-01" / "smartmeter.csv"

df = pd.read_csv(path, usecols=["time", "total_m3"])

df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
df["total_m3"] = pd.to_numeric(df["total_m3"], errors="coerce")

print("Total rows:", len(df))
print("Invalid timestamps:", df["time"].isna().sum())
print("Invalid meter readings:", df["total_m3"].isna().sum())

valid = df.dropna(subset=["time", "total_m3"]).sort_values("time")

if valid.empty:
    raise SystemExit("No valid readings found.")

print("Duplicate timestamps:", valid["time"].duplicated().sum())

# Use unique timestamps to inspect recording intervals.
readings = valid.drop_duplicates("time", keep="last").copy()
gaps = readings["time"].diff().dt.total_seconds()
changes = readings["total_m3"].diff()

print("\nFirst timestamp:", readings["time"].min())
print("Last timestamp:", readings["time"].max())
print("Typical interval (seconds):", gaps.median())
print("Longest gap (seconds):", gaps.max())
print("Gaps longer than 15 minutes:", (gaps > 900).sum())
print("Negative meter changes:", (changes < -0.000001).sum())

print("\nFirst readings where the meter increased:")
print(
    readings.loc[changes > 0, ["time", "total_m3"]]
    .head()
    .to_string(index=False)
)