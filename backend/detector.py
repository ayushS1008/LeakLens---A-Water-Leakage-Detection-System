import json
import numpy as np
import pandas as pd

MAX_INTERVALS = 25000


def prepare_readings(df, config):
    required = {"timestamp", "litres_used"}
    if not required.issubset(df.columns):
        raise ValueError(
            "CSV must contain timestamp and litres_used columns. "
            "Use the processed 15-minute CSV."
        )

    if df.empty:
        raise ValueError("The CSV is empty.")

    if len(df) > MAX_INTERVALS:
        raise ValueError("Upload at most 25,000 intervals.")

    if "household_id" in df.columns:
        if df["household_id"].dropna().nunique() > 1:
            raise ValueError("Upload one household at a time.")

    df = df.copy()

    # Require explicit timezone information.
    time_text = df["timestamp"].astype(str).str.strip()
    has_timezone = time_text.str.contains(
        r"(?:Z|[+-]\d{2}:?\d{2})$",
        regex=True,
        case=False,
    )
    if not has_timezone.all():
        raise ValueError(
            "Every timestamp needs a timezone, such as +00:00 or Z."
        )

    df["timestamp"] = pd.to_datetime(
        time_text, utc=True, errors="coerce"
    )
    if df["timestamp"].isna().any():
        raise ValueError("Invalid timestamps found.")

    original_water = df["litres_used"]
    water = pd.to_numeric(original_water, errors="coerce")

    if (original_water.notna() & water.isna()).any():
        raise ValueError("Consumption must be numeric or blank.")

    known = water.dropna()
    if not np.isfinite(known.to_numpy()).all() or (known < 0).any():
        raise ValueError("Consumption must be finite and nonnegative.")

    if "is_valid" in df.columns:
        flags = df["is_valid"].astype(str).str.strip().str.lower()
        if not flags.isin(["true", "false", "1", "0"]).all():
            raise ValueError("is_valid must contain True or False.")
        water = water.where(flags.isin(["true", "1"]))

    df["litres_used"] = water
    df = df.sort_values("timestamp")

    if df["timestamp"].duplicated().any():
        raise ValueError("Duplicate timestamps found.")

    if not df["timestamp"].eq(
        df["timestamp"].dt.floor("15min")
    ).all():
        raise ValueError("Timestamps must lie on 15-minute boundaries.")

    start = df["timestamp"].iloc[0]
    end = df["timestamp"].iloc[-1]
    interval_count = int(
        (end - start).total_seconds() / 900
    ) + 1

    if interval_count > MAX_INTERVALS:
        raise ValueError("The time range exceeds 25,000 intervals.")

    # Insert missing intervals as unknown, never as zero consumption.
    grid = pd.date_range(start, end, freq="15min")
    df = (
        df.set_index("timestamp")[["litres_used"]]
        .reindex(grid)
        .rename_axis("timestamp")
        .reset_index()
    )

    water = df["litres_used"]
    local = (
        df["timestamp"] - pd.Timedelta(minutes=15)
    ).dt.tz_convert(config["timezone"])

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

    return df, features


def analyse_readings(df, model, config):
    df, features = prepare_readings(df, config)
    water = df["litres_used"]
    columns = config["feature_columns"]
    usable = features[columns].notna().all(axis=1)

    if not usable.any():
        raise ValueError(
            "Need at least four consecutive valid 15-minute readings."
        )

    scores = pd.Series(np.nan, index=df.index)
    scores.loc[usable] = -model.score_samples(
        features.loc[usable, columns]
    )

    candidates = scores > config["anomaly_threshold"]
    alerts = (
        candidates.astype(int)
        .rolling(4, min_periods=4)
        .sum()
        .eq(4)
        & features["minimum_last_hour"].gt(0)
    )

    df["anomaly_score"] = scores
    df["is_candidate"] = candidates
    df["is_alert"] = alerts

    # Group adjacent alert intervals into one episode.
    episode_start = alerts & ~alerts.shift(fill_value=False)
    episode_ids = episode_start.cumsum()

    incidents = []
    for number, (_, group) in enumerate(
        df.loc[alerts].groupby(episode_ids.loc[alerts]),
        start=1,
    ):
        incidents.append({
            "incident_id": f"incident-{number:04d}",
            "first_alert_at": group["timestamp"].iloc[0].isoformat(),
            "last_alert_at": group["timestamp"].iloc[-1].isoformat(),
            "alert_intervals": int(len(group)),
            "status": "suspected",
        })

    return {
        "summary": {
            "total_intervals": int(len(df)),
            "valid_intervals": int(water.notna().sum()),
            "unknown_intervals": int(water.isna().sum()),
            "scored_intervals": int(usable.sum()),
            "candidate_intervals": int(candidates.sum()),
            "alert_episodes": len(incidents),
            "total_recorded_litres": float(water.sum()),
        },
        "anomaly_threshold": float(config["anomaly_threshold"]),
        "model_scope": "Prototype trained on household hh-01.",
        "incidents": incidents,
        # pandas converts missing scores/readings to JSON null.
        "readings": json.loads(
            df.to_json(orient="records", date_format="iso")
        ),
    }