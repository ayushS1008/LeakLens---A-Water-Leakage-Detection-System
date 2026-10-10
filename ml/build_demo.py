"""Build an explicitly synthetic leak-and-repair demonstration; never retrain."""
from pathlib import Path
import json
import sys
import joblib
import pandas as pd

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from backend.detector import analyse_readings


def main():
    model = joblib.load(root / 'models/isolation_forest.joblib')
    config = json.loads((root / 'models/detection_config.json').read_text())
    frame = pd.read_csv(root / 'data/processed/hh01_15min.csv')
    frame['timestamp'] = pd.to_datetime(frame['timestamp'], utc=True)
    frame = frame[frame['timestamp'] >= pd.Timestamp('2021-05-28T00:00:00Z')].reset_index(drop=True)
    chosen = None
    for offset in range(0, len(frame) - 197, 96):
        window = frame.iloc[offset:offset + 197].copy()
        if not window['is_valid'].eq(True).all() or window['litres_used'].isna().any():
            continue
        repair = window['timestamp'].iloc[100]
        before = window.iloc[:101].copy()
        # One hour of context precedes the 24-hour comparison window.
        before.loc[before.index[5:], 'litres_used'] += 15.0
        after = window.iloc[97:].copy()
        source = analyse_readings(before, model, config)
        followup = analyse_readings(after, model, config)
        if source['incidents'] and not any(row['is_alert'] for row in followup['readings'] if pd.Timestamp(row['timestamp']) > repair):
            chosen = (before, after, repair)
            break
    if chosen is None:
        raise SystemExit('No complete demonstration window found. Model and settings were not changed.')
    before, after, repair = chosen
    folder = root / 'data/demo'
    folder.mkdir(parents=True, exist_ok=True)
    before.to_csv(folder / 'leak_before_repair.csv', index=False)
    after.to_csv(folder / 'followup_after_repair.csv', index=False)
    instructions = {'synthetic_demo': True, 'description': 'A constant 1 L/min leak is added to 24 hours of real household data, then removed to represent a repair. This is an illustrative scenario, not a verified real repair.', 'repair_time_utc': repair.isoformat(), 'repair_time_for_dashboard': repair.strftime('%Y-%m-%dT%H:%M'), 'before_csv': 'leak_before_repair.csv', 'followup_csv': 'followup_after_repair.csv', 'model_settings_changed': False, 'data_source': 'https://doi.org/10.5281/zenodo.7506076', 'data_license': 'CC BY 4.0'}
    (folder / 'demo_instructions.json').write_text(json.dumps(instructions, indent=2))
    print(json.dumps(instructions, indent=2))


if __name__ == '__main__':
    main()
