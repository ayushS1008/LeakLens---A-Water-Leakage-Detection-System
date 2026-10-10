from pathlib import Path
import pandas as pd

project_root = Path(__file__).resolve().parents[1]
files = list((project_root / "data").rglob("smartmeter.csv"))

if not files:
    raise SystemExit("smartmeter.csv not found. Extract the ZIP inside data/.")

csv_path = files[0]
print("File:", csv_path)

print("\nFirst five raw lines:")
with csv_path.open(encoding="utf-8-sig") as file:
    for _ in range(5):
        print(file.readline().rstrip())

# Preview only; automatically detect the separator.
df = pd.read_csv(csv_path, sep=None, engine="python", nrows=1000)

print("\nColumns:", df.columns.tolist())
print("\nFirst five rows:")
print(df.head().to_string(index=False))
print("\nData types:")
print(df.dtypes)