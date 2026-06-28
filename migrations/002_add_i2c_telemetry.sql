ALTER TABLE temperature_readings
ADD COLUMN aht20_temperature_c REAL;

ALTER TABLE temperature_readings
ADD COLUMN aht20_humidity_percent REAL;

ALTER TABLE temperature_readings
ADD COLUMN bmp280_temperature_c REAL;

ALTER TABLE temperature_readings
ADD COLUMN bmp280_pressure_hpa REAL;

ALTER TABLE temperature_readings
ADD COLUMN ambient_error TEXT;
