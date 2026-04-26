CREATE TABLE temperature_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
    temperature_c REAL,
    relay_on INTEGER NOT NULL CHECK (relay_on IN (0, 1)),
    sensor_id TEXT,
    error TEXT
);

CREATE INDEX idx_temperature_readings_recorded_at
ON temperature_readings (recorded_at DESC);

CREATE TABLE relay_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
    relay_on INTEGER NOT NULL CHECK (relay_on IN (0, 1)),
    reason TEXT NOT NULL,
    temperature_c REAL
);

CREATE INDEX idx_relay_events_recorded_at
ON relay_events (recorded_at DESC);
