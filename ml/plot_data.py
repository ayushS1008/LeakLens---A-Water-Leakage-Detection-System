from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
source = root / "data" / "processed" / "hh01_15min.csv"
output = root / "data" / "processed" / "hh01_consumption.png"

df = pd.read_csv(source)
df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

# Display this German household's readings in local time.
df["timestamp"] = df["timestamp"].dt.tz_convert("Europe/Berlin")
df = df.sort_values("timestamp").set_index("timestamp")

# Missing consumption remains missing, not zero.
valid = df["litres_used"].dropna()

if valid.empty:
    raise SystemExit("No usable consumption readings found.")

print("Intervals with zero recorded consumption:", (valid == 0).sum())
print("Intervals with positive consumption:", (valid > 0).sum())
print("Median litres per interval:", round(valid.median(), 2))
print("95th percentile:", round(valid.quantile(0.95), 2))
print("Maximum litres per interval:", round(valid.max(), 2))

print("\nFive largest readings:")
print(valid.nlargest(5).to_string())

# Show the full history and the first seven days.
first_week = df.loc[
    df.index < df.index.min() + pd.Timedelta(days=7)
]

fig, axes = plt.subplots(2, 1, figsize=(12, 8))

axes[0].plot(df.index, df["litres_used"], linewidth=0.6)
axes[0].set_title("Household hh-01: full consumption history")

axes[1].plot(
    first_week.index,
    first_week["litres_used"],
    linewidth=1,
)
axes[1].set_title("First seven days")

for axis in axes:
    axis.set_ylabel("Litres per 15-minute interval")
    axis.set_xlabel("Time — Europe/Berlin")
    axis.grid(alpha=0.3)
    axis.tick_params(axis="x", rotation=20)

fig.tight_layout()
fig.savefig(output, dpi=150)
plt.close(fig)

print("\nChart saved:", output)