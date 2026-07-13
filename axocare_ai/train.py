"""Train local Axocare temperature prediction models."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from axocare_ai.db import load_temperature_history
from axocare_ai.features import FEATURE_COLUMNS, build_training_frame

DEFAULT_DB_PATH = "axocare.db"
DEFAULT_OUTPUT_DIR = Path("axocare_ai/models")
DEFAULT_HORIZONS = (10, 15)
DEFAULT_ALPHA = 1.0


def train_model(
    db_path: str | Path,
    horizon_minutes: int,
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    alpha: float = DEFAULT_ALPHA,
    write_model: bool = True,
) -> dict[str, Any]:
    """Train and optionally persist one thermal ridge model."""
    readings = load_temperature_history(db_path)
    dataset = build_training_frame(readings, horizon_minutes)
    if len(dataset) < 40:
        raise ValueError(
            f"Not enough training rows for {horizon_minutes}-minute horizon: "
            f"expected at least 40, found {len(dataset)}."
        )

    split_index = max(1, int(len(dataset) * 0.8))
    if split_index >= len(dataset):
        split_index = len(dataset) - 1

    train_frame = dataset.iloc[:split_index].copy()
    test_frame = dataset.iloc[split_index:].copy()
    if test_frame.empty:
        raise ValueError("A chronological test split could not be created from the available data.")

    X_train = train_frame.loc[:, FEATURE_COLUMNS].to_numpy(dtype=float)
    y_train = train_frame["target_temperature_c"].to_numpy(dtype=float)
    X_test = test_frame.loc[:, FEATURE_COLUMNS].to_numpy(dtype=float)
    y_test = test_frame["target_temperature_c"].to_numpy(dtype=float)

    trained = _fit_ridge(X_train, y_train, alpha=alpha)
    baseline_predictions = test_frame["temperature_c"].to_numpy(dtype=float)
    model_predictions = _predict_matrix(X_test, trained)

    payload = {
        "model_name": "thermal_ridge",
        "model_version": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "trained_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "horizon_minutes": horizon_minutes,
        "alpha": alpha,
        "feature_names": FEATURE_COLUMNS,
        "coefficients": trained["coefficients"].tolist(),
        "feature_means": trained["feature_means"].tolist(),
        "feature_scales": trained["feature_scales"].tolist(),
        "intercept": trained["intercept"],
        "training_rows": int(len(train_frame)),
        "testing_rows": int(len(test_frame)),
        "total_rows": int(len(dataset)),
        "metrics": {
            "baseline": _metrics(y_test, baseline_predictions),
            "thermal_ridge": _metrics(y_test, model_predictions),
        },
        "ambient_missing_rows": {
            "room_temperature": int(dataset["room_temperature_missing"].sum()),
            "humidity": int(dataset["humidity_missing"].sum()),
            "pressure": int(dataset["pressure_missing"].sum()),
        },
    }

    if write_model:
        output_path = _model_path(output_dir, horizon_minutes)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        payload["model_path"] = str(output_path)

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Train local Axocare temperature models.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to the Axocare SQLite database.")
    parser.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=list(DEFAULT_HORIZONS),
        help="Prediction horizons in minutes.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where trained model JSON files will be written.",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=DEFAULT_ALPHA,
        help="Ridge regularization strength.",
    )
    args = parser.parse_args()

    results = [
        train_model(args.db, horizon, output_dir=args.output_dir, alpha=args.alpha)
        for horizon in args.horizons
    ]
    print(json.dumps({"models": results}, indent=2))


def _fit_ridge(X: np.ndarray, y: np.ndarray, *, alpha: float) -> dict[str, np.ndarray | float]:
    feature_means = X.mean(axis=0)
    feature_scales = X.std(axis=0)
    feature_scales[feature_scales == 0] = 1.0

    X_scaled = (X - feature_means) / feature_scales
    y_centered = y - y.mean()

    identity = np.eye(X_scaled.shape[1])
    coefficients = np.linalg.solve(
        X_scaled.T @ X_scaled + alpha * identity,
        X_scaled.T @ y_centered,
    )
    return {
        "coefficients": coefficients,
        "feature_means": feature_means,
        "feature_scales": feature_scales,
        "intercept": float(y.mean()),
    }


def _predict_matrix(X: np.ndarray, trained: dict[str, np.ndarray | float]) -> np.ndarray:
    means = np.asarray(trained["feature_means"], dtype=float)
    scales = np.asarray(trained["feature_scales"], dtype=float)
    coefficients = np.asarray(trained["coefficients"], dtype=float)
    intercept = float(trained["intercept"])
    return intercept + ((X - means) / scales) @ coefficients


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    errors = predicted - actual
    return {
        "mae": round(float(np.mean(np.abs(errors))), 4),
        "rmse": round(float(np.sqrt(np.mean(errors**2))), 4),
        "max_abs_error": round(float(np.max(np.abs(errors))), 4),
    }


def _model_path(output_dir: str | Path, horizon_minutes: int) -> Path:
    return Path(output_dir) / f"thermal_ridge_h{horizon_minutes}.json"


if __name__ == "__main__":
    main()

