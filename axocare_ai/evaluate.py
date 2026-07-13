"""Evaluate local Axocare temperature prediction models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from axocare_ai.train import DEFAULT_DB_PATH, DEFAULT_HORIZONS, train_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Axocare temperature models.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to the Axocare SQLite database.")
    parser.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=list(DEFAULT_HORIZONS),
        help="Prediction horizons in minutes.",
    )
    parser.add_argument(
        "--models-dir",
        default="axocare_ai/models",
        help="Optional models directory to mirror the training command signature.",
    )
    args = parser.parse_args()

    evaluations = [
        train_model(args.db, horizon, output_dir=Path(args.models_dir), write_model=False)
        for horizon in args.horizons
    ]
    print(json.dumps({"evaluations": evaluations}, indent=2))


if __name__ == "__main__":
    main()

