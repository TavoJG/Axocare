# Axocare AI

`axocare_ai` is the local prediction layer for Axocare.

Its job is simple: look at recent aquarium telemetry and estimate what the
water temperature will be in the next few minutes. This does not replace the
existing relay-based cooling control. Instead, it adds a forecasting layer that
helps the system answer questions like:

- Is the aquarium likely to warm up in the next 10 to 15 minutes?
- Is the temperature staying stable?
- Is there early risk of moving toward an unsafe range?

The package is designed to work entirely offline using the Axocare SQLite
database, so the model can be trained and used directly on the device.

## What Problem This Solves

Axolotl aquariums are slow thermal systems. By the time a human notices that
the water is drifting in the wrong direction, the trend may have already been
developing for a while.

This package helps Axocare move from only reporting the current state to also
estimating the near-future state.

That makes it useful for:

- Short-term forecasting of water temperature
- Explaining whether the system looks stable or unstable
- Giving the MCP server a grounded prediction tool for the aquarium assistant
- Comparing a learned model against a simple baseline

In other words, this package answers:

`What will the water temperature probably be soon, based on what has been happening recently?`

## How It Works

The workflow has three steps:

1. Load historical telemetry from `temperature_readings` in SQLite.
2. Turn that history into training features.
3. Train a small local regression model and save it as JSON.

Later, when a prediction is requested, the package:

1. Loads the latest telemetry from the database
2. Builds the same feature set for the newest valid row
3. Loads the saved model
4. Produces a predicted future temperature for the requested horizon

## Which Data Is Used

The trainer reads historical rows from the `temperature_readings` table and
uses these signals:

- `temperature_c`
- `relay_on`
- `room_temperature`
- `aht20_humidity_percent`
- `bmp280_pressure_hpa`
- `recorded_at`

The most important signal is still the aquarium water temperature itself. The
ambient readings and cooling state help the model understand why the water may
be warming, cooling, or staying flat.

## How Features Are Built

The model does not learn from a single row in isolation. It learns from the
recent pattern leading up to that row.

For each usable reading, the feature builder creates values such as:

- Current aquarium temperature
- Recent lag values like 1, 5, 10, and 15 minutes ago
- Rolling averages over the last 5, 10, and 15 readings
- Recent slopes such as how much the temperature changed in the last 10 minutes
- How many of the last 10 or 15 readings had cooling enabled
- Time-of-day context like hour, day of week, and whether it is nighttime
- Ambient telemetry with missingness indicators

This helps the model answer questions like:

- Is the water already trending upward?
- Has cooling been active recently?
- Is the room warmer than usual?
- Is this part of the daily temperature pattern?

## How Missing Ambient Data Is Handled

This is an important part of the implementation.

Older database rows may have `NULL` values for `room_temperature`,
`aht20_humidity_percent`, or pressure because those sensors were added later.
If we simply discarded every row with missing ambient data, we would lose a lot
of useful history.

Instead, the package keeps those rows and handles them defensively:

- Rows with missing `temperature_c` are dropped because the target signal is essential
- Ambient values are filled using nearby valid readings when possible
- If there is still no value, safe fallback values are used
- Extra flags such as `room_temperature_missing` and `humidity_missing` are added

This gives the model two benefits:

- It can still learn from older water temperature history
- It can also learn that some ambient inputs were missing, instead of treating them as real sensor values

## How Training Works

Training is done locally with a small ridge regression model called
`thermal_ridge`.

Ridge regression is a good fit here because:

- The problem is short-horizon forecasting, not image recognition or large-scale deep learning
- The aquarium is a slow physical system
- We want a lightweight model that is easy to train and run on-device
- Regularization helps keep the model more stable and less prone to overfitting

The package trains one model per forecast horizon. Right now the main horizons
are:

- 10 minutes
- 15 minutes

Each training example is built like this:

- Start with a current row and its recent context
- Look forward by the target horizon
- Find the future aquarium temperature near that timestamp
- Use the current context as input and the future temperature as the label

The current implementation allows a small timestamp tolerance when matching
future rows, which helps because real sensor logging is not always perfectly
aligned to the exact second.

## How the Train/Test Split Works

This project uses a chronological split, not a random split.

That means:

- The first 80% of usable rows are used for training
- The last 20% are used for testing

This is important for time-series problems. In real life, we always use the
past to predict the future. A random split would mix older and newer data
together and make the evaluation less realistic.

## How the Model Is Evaluated

After training, the package compares two approaches on the held-out test data:

- `baseline`: predict that the future temperature will be the same as the current temperature
- `thermal_ridge`: use the trained regression model

The metrics reported are:

- `MAE` (mean absolute error)
- `RMSE` (root mean squared error)
- `max_abs_error`

This comparison matters because aquarium temperature changes slowly. A model is
only useful if it beats the simple “future equals current” baseline often
enough to justify the extra complexity.

## Saved Model Format

Each trained model is saved as a JSON file in `axocare_ai/models/`.

The file stores:

- Model name and version
- Horizon in minutes
- Feature names
- Coefficients
- Normalization statistics
- Train/test counts
- Evaluation metrics
- Counts of rows that had missing ambient values

This makes the model easy to inspect, easy to copy, and easy to use without
introducing a heavy runtime dependency.

## Commands

### Train Models

```bash
python -m axocare_ai.train \
  --db ./axocare.db \
  --horizons 10 15 \
  --output-dir ./axocare_ai/models
```

This reads historical telemetry, builds supervised datasets for each requested
horizon, trains the models, evaluates them, and writes JSON artifacts to the
models directory.

### Evaluate Models

```bash
python -m axocare_ai.evaluate --db ./axocare.db --horizons 10 15
```

This reruns the training logic in evaluation mode and prints the metrics without
rewriting model artifacts.

### Predict Current Temperature

```bash
python -m axocare_ai.predict --db ./axocare.db --horizon 15
```

This loads the trained model for the requested horizon, builds features from the
latest valid telemetry, and returns a JSON prediction.

## Example Prediction Output

```json
{
  "available": true,
  "recorded_at": "2026-07-13T16:11:29Z",
  "current_temperature_c": 19.312,
  "predicted_temperature_c": 19.369,
  "horizon_minutes": 15,
  "cooling_on": false,
  "room_temperature_c": 25.308,
  "humidity_percent": 51.874,
  "risk_level": "low",
  "model_name": "thermal_ridge"
}
```

## Risk Levels

Predictions are classified into simple risk bands:

- `low` for temperatures below `20.0 C`
- `medium` for temperatures from `20.0 C` up to but not including `21.0 C`
- `high` for temperatures `21.0 C` and above

These thresholds are intentionally simple. They can be adjusted later as the
project evolves.

## Design Goals

This package was built with a few practical goals in mind:

- Run locally on Axocare hardware
- Work with imperfect real-world telemetry
- Remain understandable and inspectable
- Produce short-horizon predictions rather than overly ambitious long-range forecasts
- Support the MCP server and aquarium assistant with grounded, explainable estimates

## Important Limitation

This model produces estimates, not guarantees.

It should be understood as a short-term forecasting tool based on recent
patterns in telemetry. It is useful for monitoring and explanation, but it does
not replace sensor readings, safety logic, or the existing cooling controller.
