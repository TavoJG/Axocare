"""Run local Axocare temperature predictions from trained model artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from axocare_ai.db import load_temperature_history
from axocare_ai.features import FEATURE_COLUMNS, build_live_feature_row

DEFAULT_DB_PATH = "axocare.db"
DEFAULT_MODELS_DIR = Path("axocare_ai/models")


def predict_from_db(
    db_path: str | Path,
    horizon_minutes: int,
    *,
    models_dir: str | Path = DEFAULT_MODELS_DIR,
) -> dict[str, Any]:
    """Predict future aquarium temperature from the latest valid reading."""
    model_path = Path(models_dir) / f"thermal_ridge_h{horizon_minutes}.json"
    if not model_path.exists():
        return {
            "available": False,
            "horizon_minutes": horizon_minutes,
            "message": (
                f"No trained temperature model is available for the {horizon_minutes}-minute "
                f"horizon at {model_path}."
            ),
        }

    model = json.loads(model_path.read_text(encoding="utf-8"))
    readings = load_temperature_history(db_path)
    live_row = build_live_feature_row(readings)
    if live_row is None:
        return {
            "available": False,
            "horizon_minutes": horizon_minutes,
            "message": (
                "Not enough recent valid telemetry is available to build prediction features. "
                "At least 15 valid aquarium readings are required."
            ),
        }

    X = live_row.features.loc[:, FEATURE_COLUMNS].to_numpy(dtype=float)
    prediction = _predict_matrix(X, model)[0]
    current_temperature = float(live_row.context["current_temperature_c"])
    risk_level = _risk_level(prediction)
    return {
        "available": True,
        "recorded_at": live_row.context["recorded_at"],
        "current_temperature_c": round(current_temperature, 3),
        "predicted_temperature_c": round(float(prediction), 3),
        "horizon_minutes": horizon_minutes,
        "cooling_on": bool(live_row.context["cooling_on"]),
        "room_temperature_c": live_row.context["room_temperature_c"],
        "humidity_percent": live_row.context["humidity_percent"],
        "risk_level": risk_level,
        "model_name": model["model_name"],
        "model_version": model["model_version"],
        "explanation": _explanation(
            current_temperature=current_temperature,
            predicted_temperature=float(prediction),
            cooling_on=bool(live_row.context["cooling_on"]),
            temp_slope_10=float(live_row.context["temp_slope_10"]),
            room_temperature_missing=bool(live_row.context["room_temperature_missing"]),
        ),
        "metrics": model.get("metrics", {}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict Axocare temperature from a local model.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to the Axocare SQLite database.")
    parser.add_argument("--horizon", type=int, required=True, help="Prediction horizon in minutes.")
    parser.add_argument(
        "--models-dir",
        default=str(DEFAULT_MODELS_DIR),
        help="Directory containing trained model JSON files.",
    )
    args = parser.parse_args()

    print(json.dumps(predict_from_db(args.db, args.horizon, models_dir=args.models_dir), indent=2))


def _predict_matrix(X: np.ndarray, model: dict[str, Any]) -> np.ndarray:
    means = np.asarray(model["feature_means"], dtype=float)
    scales = np.asarray(model["feature_scales"], dtype=float)
    coefficients = np.asarray(model["coefficients"], dtype=float)
    intercept = float(model["intercept"])
    return intercept + ((X - means) / scales) @ coefficients


def _risk_level(predicted_temperature_c: float) -> str:
    if predicted_temperature_c >= 21.0:
        return "high"
    if predicted_temperature_c >= 20.0:
        return "medium"
    return "low"


def _explanation(
    *,
    current_temperature: float,
    predicted_temperature: float,
    cooling_on: bool,
    temp_slope_10: float,
    room_temperature_missing: bool,
) -> str:
    delta = predicted_temperature - current_temperature
    if delta > 0.12:
        direction = "slightly warmer"
    elif delta < -0.12:
        direction = "slightly cooler"
    else:
        direction = "nearly unchanged"

    trend = (
        "rising"
        if temp_slope_10 > 0.12
        else "falling"
        if temp_slope_10 < -0.12
        else "stable"
    )
    ambient_note = (
        " Ambient room telemetry is missing in the latest reading, so the estimate leans more on "
        "recent water temperature and cooling activity."
        if room_temperature_missing
        else ""
    )
    cooling_note = "The cooling system is currently active." if cooling_on else "The cooling system is currently off."
    return (
        f"The model expects the aquarium to remain {direction} over the next period. "
        f"Recent 10-minute trend is {trend}. {cooling_note}{ambient_note}"
    )


if __name__ == "__main__":
    main()

