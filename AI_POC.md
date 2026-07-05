# Axocare AI Proof of Concept

## 1. Project Context

Axocare is an aquarium monitoring and temperature control system running on a Raspberry Pi 4.

The system monitors an axolotl aquarium and controls a cooling system using a relay shield. The relay activates both:

* a 12 V DC fan
* a Peltier cooling unit

The system records sensor data once per minute into a local SQLite database.

The current objective is to build an AI Proof of Concept with two main components:

1. A short-term temperature prediction model.
2. An AI agent that can answer aquarium-related questions by consuming a custom MCP server.

---

## 2. Current Hardware

* Raspberry Pi 4
* Three-relay shield
* DS18B20 temperature sensor for aquarium water temperature
* AHT20 + BMP280 I2C sensor module for room/environmental telemetry
* Relay-controlled cooling system:

  * fan
  * Peltier cooler
* SQLite3 database
* PushOver alerts for threshold violations

---

## 3. Current Database

The database migrations are located in:

```text
migrations/
```

The main table for the AI POC is:

```sql
temperature_readings
```

Relevant fields:

```text
recorded_at
temperature_c
relay_on
sensor_id
error
room_temperature
aht20_humidity_percent
bmp280_temperature_c
bmp280_pressure_hpa
ambient_error
```

Important clarification:

```text
relay_on does not mean only "fan on".
relay_on means the complete cooling system is active.
When relay_on = 1, both the fan and the Peltier cooler are ON.
When relay_on = 0, both are OFF.
```

For code readability, the ML and MCP layers may refer to this as:

```text
cooling_on
```

But the database column should remain:

```text
relay_on
```

---

## 4. POC Goal

The goal is not to replace the current relay-based temperature control logic.

The goal is to add an AI layer capable of:

1. Predicting aquarium water temperature 10 to 15 minutes into the future.
2. Explaining whether the system appears stable.
3. Detecting early risk of temperature deviation.
4. Answering natural language questions about the aquarium using MCP tools.

---

## 5. Available Data

At the time of the presentation, only about two weeks of data will be available.

Because of this limitation, avoid relying only on a large machine learning model.

The recommended approach is:

```text
Primary model:
    Simple thermal regression / physics-inspired model

Experimental comparison:
    Random Forest or Gradient Boosting model

Baseline:
    Naive prediction: future temperature equals current temperature
```

The model horizon should be limited to:

```text
10 minutes
15 minutes
```

A 30-minute prediction may be included as experimental, but should not be presented as the main reliable output.

---

## 6. Prediction Targets

Create supervised learning targets by shifting `temperature_c` into the future.

Required targets:

```text
temperature_c_10min_future
temperature_c_15min_future
```

Optional target:

```text
temperature_c_30min_future
```

Each row should use the current and recent historical state to predict the future water temperature.

---

## 7. Recommended Features

Create a feature engineering module that generates the following features from `temperature_readings`.

Raw features:

```text
temperature_c
room_temperature
aht20_humidity_percent
bmp280_pressure_hpa
relay_on
```

Derived features:

```text
temp_lag_1
temp_lag_5
temp_lag_10
temp_lag_15

temp_avg_5
temp_avg_10
temp_avg_15

temp_slope_5
temp_slope_10
temp_slope_15

room_temp_lag_5
room_temp_avg_10

cooling_minutes_on_last_10
cooling_minutes_on_last_15

hour
day_of_week
is_night
```

Definitions:

```text
temp_lag_5:
    aquarium temperature 5 minutes before the current row

temp_avg_10:
    rolling average of aquarium temperature over the last 10 minutes

temp_slope_10:
    temperature_c - temp_lag_10

cooling_minutes_on_last_15:
    number of minutes during the last 15 readings where relay_on = 1

is_night:
    true when hour is between 20:00 and 07:00
```

---

## 8. Models to Implement

### 8.1 Baseline Model

The baseline prediction is:

```text
predicted_temperature = current temperature
```

This is important because the aquarium is a slow thermal system. A model is only useful if it beats this baseline.

---

### 8.2 Thermal Regression Model

Implement a simple physically-inspired regression.

Suggested equation:

```text
T_future = T_current
           + alpha * (room_temperature - T_current)
           - beta * cooling_on
           + gamma * temp_slope_10
           + bias
```

Where:

```text
T_current = current aquarium temperature
room_temperature = current room temperature
cooling_on = relay_on
temp_slope_10 = recent aquarium temperature trend
```

This can be implemented using:

```python
sklearn.linear_model.Ridge
```

or:

```python
sklearn.linear_model.LinearRegression
```

Prefer Ridge regression to reduce overfitting.

---

### 8.3 Random Forest Model

Implement a Random Forest as an experimental comparison.

Suggested configuration:

```python
RandomForestRegressor(
    n_estimators=300,
    max_depth=8,
    min_samples_leaf=5,
    random_state=42,
    n_jobs=-1
)
```

The Random Forest should not be presented as the only AI model because two weeks of data may not be enough to generalize well.

---

## 9. Evaluation

Do not use random train/test splitting.

Because this is time-series data, use chronological splitting:

```text
First 80% of rows:
    training

Last 20% of rows:
    testing
```

Metrics:

```text
MAE
RMSE
Max absolute error
```

Compare:

```text
Baseline
Thermal regression
Random Forest
```

Example output:

```text
Horizon: 15 minutes

Model                 MAE      RMSE
Baseline              0.18     0.23
Thermal Regression    0.11     0.15
Random Forest         0.13     0.18
```

---

## 10. Prediction Risk Classification

Create a simple risk classifier based on predicted temperature.

Suggested thresholds:

```text
low:
    predicted temperature < 20.0 °C

medium:
    predicted temperature >= 20.0 °C and < 21.0 °C

high:
    predicted temperature >= 21.0 °C
```

These thresholds may be adjusted later.

Example prediction output:

```json
{
  "current_temperature_c": 19.4,
  "horizon_minutes": 15,
  "predicted_temperature_c": 19.7,
  "cooling_on": true,
  "risk_level": "low",
  "model_name": "thermal_ridge",
  "explanation": "The aquarium temperature is stable. The cooling system is active and the recent 10-minute trend is nearly flat."
}
```

---

## 11. Suggested Project Structure

Add the following structure to the repository:

```text
axocare_ai/
├── __init__.py
├── db.py
├── features.py
├── train.py
├── predict.py
├── evaluate.py
├── models/
│   └── .gitkeep
└── README.md

mcp_server/
├── __init__.py
├── server.py
├── tools.py
├── db.py
└── README.md
```

---

## 12. AI Model CLI Commands

Implement the following commands.

### Train models

```bash
python -m axocare_ai.train \
  --db ./axocare.db \
  --horizons 10 15 \
  --output-dir ./axocare_ai/models
```

### Evaluate models

```bash
python -m axocare_ai.evaluate \
  --db ./axocare.db \
  --models-dir ./axocare_ai/models
```

### Predict current temperature

```bash
python -m axocare_ai.predict \
  --db ./axocare.db \
  --horizon 15
```

Expected output:

```json
{
  "current_temperature_c": 19.4,
  "predicted_temperature_c": 19.6,
  "horizon_minutes": 15,
  "cooling_on": true,
  "risk_level": "low",
  "model_name": "thermal_ridge"
}
```

---

## 13. Optional Database Table for Predictions

Add a new migration only if prediction history should be stored.

```sql
CREATE TABLE IF NOT EXISTS temperature_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
    horizon_minutes INTEGER NOT NULL,
    current_temperature_c REAL NOT NULL,
    predicted_temperature_c REAL NOT NULL,
    cooling_on INTEGER NOT NULL CHECK (cooling_on IN (0, 1)),
    model_name TEXT NOT NULL,
    model_version TEXT,
    risk_level TEXT,
    explanation TEXT
);

CREATE INDEX IF NOT EXISTS idx_temperature_predictions_recorded_at
ON temperature_predictions (recorded_at DESC);
```

---

## 14. MCP Server Goal

Create a local MCP server that exposes aquarium data and prediction capabilities to an AI agent.

The agent should not access SQLite directly.

The agent should only interact through MCP tools.

---

## 15. Required MCP Tools

Implement the following MCP tools.

### 15.1 get_current_status

Returns the latest available aquarium status.

Input:

```json
{}
```

Output:

```json
{
  "recorded_at": "2026-07-04T11:42:00",
  "aquarium_temperature_c": 19.4,
  "cooling_on": true,
  "room_temperature_c": 24.8,
  "humidity_percent": 48.2,
  "pressure_hpa": 1012.4,
  "sensor_error": null,
  "ambient_error": null
}
```

---

### 15.2 get_recent_readings

Returns recent temperature readings.

Input:

```json
{
  "minutes": 60
}
```

Output:

```json
{
  "minutes": 60,
  "readings": [
    {
      "recorded_at": "2026-07-04T11:00:00",
      "aquarium_temperature_c": 19.3,
      "cooling_on": false,
      "room_temperature_c": 24.7,
      "humidity_percent": 48.0,
      "pressure_hpa": 1012.2
    }
  ]
}
```

---

### 15.3 get_temperature_summary

Returns aggregate statistics for a period.

Input:

```json
{
  "hours": 24
}
```

Output:

```json
{
  "hours": 24,
  "min_temperature_c": 18.8,
  "max_temperature_c": 19.9,
  "avg_temperature_c": 19.3,
  "latest_temperature_c": 19.4,
  "cooling_on_minutes": 320,
  "cooling_on_percent": 22.2
}
```

---

### 15.4 get_relay_events

Returns relay/cooling state changes.

Input:

```json
{
  "hours": 24
}
```

Output:

```json
{
  "hours": 24,
  "events": [
    {
      "recorded_at": "2026-07-04T10:12:00",
      "relay_on": true,
      "reason": "temperature_above_threshold",
      "temperature_c": 19.6
    }
  ]
}
```

---

### 15.5 predict_temperature

Runs the local prediction model.

Input:

```json
{
  "horizon_minutes": 15
}
```

Output:

```json
{
  "current_temperature_c": 19.4,
  "predicted_temperature_c": 19.6,
  "horizon_minutes": 15,
  "cooling_on": true,
  "risk_level": "low",
  "model_name": "thermal_ridge",
  "explanation": "Temperature is expected to remain stable over the next 15 minutes."
}
```

---

### 15.6 explain_temperature_trend

Explains recent behavior in natural-language-friendly structured data.

Input:

```json
{
  "minutes": 60
}
```

Output:

```json
{
  "minutes": 60,
  "trend": "stable",
  "temperature_change_c": 0.1,
  "cooling_on_percent": 30.0,
  "summary": "The aquarium temperature has remained nearly stable over the last hour. The cooling system was active for about 30% of the period."
}
```

---

## 16. Example Questions the AI Agent Should Answer

The AI agent should be able to answer questions like:

```text
How is the aquarium right now?
Is the water temperature rising or falling?
Is the cooling system working?
How much time was the cooling system on today?
What was the maximum temperature in the last 24 hours?
Is there a risk that the aquarium will exceed 21 °C?
What does the model predict for the next 15 minutes?
Was the system stable overnight?
Did the room temperature affect the aquarium temperature today?
```

---

## 17. Agent Behavior

The AI agent should:

1. Use MCP tools instead of guessing.
2. Mention when data is missing or stale.
3. Explain predictions as estimates, not certainties.
4. Avoid making health claims about the axolotl unless the data clearly supports a temperature-related risk.
5. Distinguish between:

   * current state
   * historical summary
   * prediction
   * recommendation

Example answer:

```text
The aquarium is currently at 19.4 °C and the cooling system is ON.
Over the last hour, the temperature changed by only +0.1 °C, so the trend appears stable.
The 15-minute model predicts 19.6 °C, which remains in the low-risk range.
```

---

## 18. Success Criteria for the POC

The POC is successful if it can:

1. Load historical data from SQLite.
2. Build a valid ML dataset from `temperature_readings`.
3. Train at least:

   * baseline
   * thermal regression
   * Random Forest
4. Evaluate models using chronological train/test split.
5. Predict the aquarium temperature 10 and 15 minutes into the future.
6. Classify temperature risk.
7. Expose aquarium data through MCP tools.
8. Allow an AI agent to answer questions using the MCP server.

---

## 19. Recommended Implementation Order

Implement in this order:

```text
1. axocare_ai/db.py
2. axocare_ai/features.py
3. axocare_ai/train.py
4. axocare_ai/evaluate.py
5. axocare_ai/predict.py
6. mcp_server/db.py
7. mcp_server/tools.py
8. mcp_server/server.py
9. README usage examples
```

---

## 20. Notes for Codex

When implementing, avoid modifying the existing control logic unless explicitly requested.

Do not rename the existing database column `relay_on`.

Inside Python code, it is acceptable to map:

```python
cooling_on = relay_on
```

Use defensive handling for missing environmental values.

Rows with missing `temperature_c` or invalid timestamps should be ignored during training.

The model should be usable locally without requiring cloud services.

The MCP server should be model-agnostic so it can be used by either:

```text
OpenAI / ChatGPT agent
Ollama local model
other MCP-compatible clients
```
