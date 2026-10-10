"""Create an independent, versioned detector from each household's history."""
from io import BytesIO
import hashlib
import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from backend.detector import prepare_readings
from backend.workflow import utc_now


def validate_identity(frame, household_id):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,39}', household_id):
        raise ValueError('Use a household ID of up to 40 letters, numbers, hyphens, or underscores.')
    if 'household_id' not in frame or frame['household_id'].isna().any():
        raise ValueError('Every row needs a household_id matching the selected household.')
    ids = frame['household_id'].astype(str).unique()
    if len(ids) != 1 or ids[0] != household_id:
        raise ValueError(f'The CSV must belong to household {household_id}. Choose the matching profile or add it first.')


def train_household(frame, household_id, name, timezone, feature_columns):
    validate_identity(frame, household_id)
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError('Enter a valid timezone, such as Asia/Kolkata or Europe/Berlin.') from error
    config = {'feature_columns': feature_columns, 'timezone': timezone, 'interval_minutes': 15, 'random_state': 42}
    grid, features = prepare_readings(frame, config)
    usable = features[feature_columns].notna().all(axis=1)
    if len(grid) < 14 * 96 or usable.mean() < .8:
        raise ValueError('Provide at least 14 days of history with 80% or more complete feature windows. More representative history is better.')
    # Split on the time grid before removing incomplete feature windows.
    boundary = int(len(grid) * .7)
    train = features.iloc[:boundary].dropna()
    validation = features.iloc[boundary:].dropna()
    if len(train) < 500 or len(validation) < 200:
        raise ValueError('Not enough complete readings for separate training and calibration periods.')
    model = IsolationForest(n_estimators=160, max_samples=min(1024, len(train)), random_state=42, contamination='auto', n_jobs=1)
    model.fit(train[feature_columns])
    threshold = float(np.quantile(-model.score_samples(validation[feature_columns]), .98))
    config.update(anomaly_threshold=threshold, training_rows=len(train), validation_rows=len(validation), threshold_method='98th percentile of later calibration readings')
    buffer = BytesIO()
    joblib.dump(model, buffer, compress=3)
    artifact = buffer.getvalue()
    fingerprint = hashlib.sha256(artifact + json.dumps(config, sort_keys=True).encode()).hexdigest()
    hourly = grid.assign(hour=(grid['timestamp'] - pd.Timedelta(minutes=15)).dt.tz_convert(timezone).dt.hour)
    medians = hourly.groupby('hour')['litres_used'].median()
    profile = {
        'household_id': household_id, 'name': name.strip(), 'timezone': timezone, 'built_in': False,
        'created_at': utc_now(), 'model_key': 'model-' + fingerprint[:32], 'model_fingerprint': fingerprint,
        'config': config, 'baseline_start': grid['timestamp'].iloc[0].isoformat(), 'baseline_end': grid['timestamp'].iloc[-1].isoformat(),
        'training_rows': len(train), 'calibration_rows': len(validation), 'valid_coverage_percent': round(float(usable.mean() * 100), 1),
        'hourly_median_litres': {str(int(hour)): float(value) for hour, value in medians.items() if pd.notna(value)},
        'model_status': 'Household-specific model; independent leak-detection evaluation is still needed.', 'revision': 0,
    }
    return profile, artifact


def public_profile(profile):
    return {key: value for key, value in profile.items() if key not in ['config', 'model_key', 'model_fingerprint']}


def explain_analysis(analysis, config, profile):
    """Describe measured conditions. These are not causal feature attributions."""
    rows = analysis['readings']
    indices = {pd.Timestamp(row['timestamp']): index for index, row in enumerate(rows)}
    threshold = analysis['anomaly_threshold']
    for incident in analysis['incidents']:
        index = indices[pd.Timestamp(incident['first_alert_at'])]
        window = rows[max(0, index - 3):index + 1]
        known = [row['litres_used'] for row in window if row['litres_used'] is not None]
        run = 0
        for row in reversed(rows[:index + 1]):
            if row['litres_used'] is None or row['litres_used'] <= 0:
                break
            run += 1
        scores = [row['anomaly_score'] for row in window if row['anomaly_score'] is not None]
        evidence = {
            'positive_use_minutes': run * 15, 'litres_in_trigger_hour': round(sum(known), 3),
            'minimum_interval_litres': round(min(known), 3) if known else None,
            'consecutive_unusual_intervals': sum(score > threshold for score in scores),
            'minimum_score': min(scores) if scores else None, 'threshold': threshold,
            'first_alert_score': rows[index]['anomaly_score'],
        }
        reasons = [
            f"All four 15-minute readings leading up to the first alert exceeded this household's anomaly threshold ({threshold:.3f}).",
            f"Water use was recorded in every interval for at least {run * 15} minutes before and including the first alert.",
            f"{sum(known):g} litres were recorded in the hour ending at the first alert.",
        ]
        hour = (pd.Timestamp(incident['first_alert_at']) - pd.Timedelta(minutes=15)).tz_convert(config['timezone']).hour
        typical = profile.get('hourly_median_litres', {}).get(str(hour))
        if typical is not None:
            evidence['typical_interval_litres_for_hour'] = typical
            reasons.append(f"The baseline median for a 15-minute interval in this local hour was {typical:g} litres. This is context, not proof of a leak.")
        incident['explanation'] = {'reasons': reasons, 'evidence': evidence, 'limitation': 'These describe the detector conditions, not a diagnosis or feature-importance calculation. Repeated ordinary use can produce the same pattern.'}
    analysis['household_name'] = profile['name']
    analysis['model_scope'] = f"Detector trained for household {profile['household_id']}."
    analysis['baseline_overlap'] = bool(profile.get('baseline_end') and pd.Timestamp(rows[0]['timestamp']) <= pd.Timestamp(profile['baseline_end']) and pd.Timestamp(rows[-1]['timestamp']) >= pd.Timestamp(profile['baseline_start']))
    return analysis
