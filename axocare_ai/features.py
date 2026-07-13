"""Feature engineering for local Axocare temperature prediction."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

FEATURE_COLUMNS = [
    "temperature_c",
    "room_temperature_filled",
    "humidity_filled",
    "pressure_filled",
    "cooling_on",
    "temp_lag_1",
    "temp_lag_5",
    "temp_lag_10",
    "temp_lag_15",
    "temp_avg_5",
    "temp_avg_10",
    "temp_avg_15",
    "temp_slope_5",
    "temp_slope_10",
    "temp_slope_15",
    "room_temp_lag_5",
    "room_temp_avg_10",
    "cooling_minutes_on_last_10",
    "cooling_minutes_on_last_15",
    "hour",
    "day_of_week",
    "is_night",
    "room_temperature_missing",
    "humidity_missing",
    "pressure_missing",
]


@dataclass(frozen=True)
class LiveFeatureRow:
    """One feature row for live prediction with a small amount of context."""

    features: pd.DataFrame
    context: dict[str, object]


def build_training_frame(readings: pd.DataFrame, horizon_minutes: int) -> pd.DataFrame:
    """Build a supervised learning frame for the requested future horizon."""
    engineered = _engineer_features(readings)
    if engineered.empty:
        return engineered

    future = (
        engineered.loc[:, ["recorded_at", "temperature_c"]]
        .rename(
            columns={
                "recorded_at": "future_recorded_at",
                "temperature_c": "target_temperature_c",
            }
        )
        .sort_values("future_recorded_at")
    )

    training = engineered.assign(
        target_timestamp=engineered["recorded_at"] + pd.Timedelta(minutes=horizon_minutes)
    ).sort_values("target_timestamp")
    merged = pd.merge_asof(
        training,
        future,
        left_on="target_timestamp",
        right_on="future_recorded_at",
        direction="forward",
        tolerance=pd.Timedelta(minutes=2),
    )
    merged["target_gap_seconds"] = (
        merged["future_recorded_at"] - merged["target_timestamp"]
    ).dt.total_seconds()
    return merged.dropna(subset=FEATURE_COLUMNS + ["target_temperature_c"]).reset_index(drop=True)


def build_live_feature_row(readings: pd.DataFrame) -> LiveFeatureRow | None:
    """Build the latest feature row used for live predictions."""
    engineered = _engineer_features(readings)
    if engineered.empty:
        return None

    latest = engineered.iloc[[-1]].copy()
    if latest[FEATURE_COLUMNS].isna().any(axis=None):
        return None

    latest_row = latest.iloc[0]
    return LiveFeatureRow(
        features=latest.loc[:, FEATURE_COLUMNS],
        context={
            "recorded_at": latest_row["recorded_at"].isoformat().replace("+00:00", "Z"),
            "current_temperature_c": round(float(latest_row["temperature_c"]), 3),
            "cooling_on": bool(latest_row["cooling_on"]),
            "room_temperature_c": _optional_round(latest_row["room_temperature_raw"]),
            "humidity_percent": _optional_round(latest_row["humidity_raw"]),
            "pressure_hpa": _optional_round(latest_row["pressure_raw"]),
            "room_temperature_missing": bool(latest_row["room_temperature_missing"]),
            "humidity_missing": bool(latest_row["humidity_missing"]),
            "pressure_missing": bool(latest_row["pressure_missing"]),
            "temp_slope_10": round(float(latest_row["temp_slope_10"]), 3),
        },
    )


def _engineer_features(readings: pd.DataFrame) -> pd.DataFrame:
    if readings.empty:
        return readings.copy()

    frame = readings.copy()
    frame = frame.dropna(subset=["temperature_c"]).copy()
    if frame.empty:
        return frame

    frame["cooling_on"] = frame["relay_on"].fillna(0).astype(int)
    frame["room_temperature_missing"] = frame["room_temperature"].isna().astype(int)
    frame["humidity_missing"] = frame["aht20_humidity_percent"].isna().astype(int)
    frame["pressure_missing"] = frame["bmp280_pressure_hpa"].isna().astype(int)

    frame["room_temperature_raw"] = frame["room_temperature"]
    frame["humidity_raw"] = frame["aht20_humidity_percent"]
    frame["pressure_raw"] = frame["bmp280_pressure_hpa"]

    frame["room_temperature_filled"] = _fill_environment_series(
        frame["room_temperature"], fallback=frame["temperature_c"]
    )
    frame["humidity_filled"] = _fill_environment_series(
        frame["aht20_humidity_percent"], fallback=50.0
    )
    frame["pressure_filled"] = _fill_environment_series(
        frame["bmp280_pressure_hpa"], fallback=1013.25
    )

    for lag in (1, 5, 10, 15):
        frame[f"temp_lag_{lag}"] = frame["temperature_c"].shift(lag)
    for window in (5, 10, 15):
        frame[f"temp_avg_{window}"] = (
            frame["temperature_c"].rolling(window=window, min_periods=window).mean()
        )
        frame[f"cooling_minutes_on_last_{window}"] = (
            frame["cooling_on"].rolling(window=window, min_periods=window).sum()
        )

    frame["temp_slope_5"] = frame["temperature_c"] - frame["temp_lag_5"]
    frame["temp_slope_10"] = frame["temperature_c"] - frame["temp_lag_10"]
    frame["temp_slope_15"] = frame["temperature_c"] - frame["temp_lag_15"]
    frame["room_temp_lag_5"] = frame["room_temperature_filled"].shift(5)
    frame["room_temp_avg_10"] = (
        frame["room_temperature_filled"].rolling(window=10, min_periods=10).mean()
    )

    frame["hour"] = frame["recorded_at"].dt.hour.astype(float)
    frame["day_of_week"] = frame["recorded_at"].dt.dayofweek.astype(float)
    frame["is_night"] = frame["hour"].apply(lambda hour: 1.0 if hour >= 20 or hour < 7 else 0.0)
    return frame


def _fill_environment_series(series: pd.Series, fallback: pd.Series | float) -> pd.Series:
    filled = series.ffill().bfill()
    if isinstance(fallback, pd.Series):
        filled = filled.fillna(fallback)
    else:
        filled = filled.fillna(float(fallback))
    return filled


def _optional_round(value: object) -> float | None:
    return round(float(value), 3) if pd.notna(value) else None

