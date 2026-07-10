import type { DashboardResponse, TemperatureReading } from "../types";

export const reading: TemperatureReading = {
  id: 1, recorded_at: "2026-01-02T03:04:00Z", temperature_c: 18.25,
  relay_on: false, sensor_id: "tank", error: null, room_temperature: 21.5,
  aht20_humidity_percent: 62.4, bmp280_temperature_c: 21.2,
  bmp280_pressure_hpa: 1012.6, ambient_error: null
};

export const dashboard: DashboardResponse = {
  db_path: "data.db", span_minutes: 60, current: reading, readings: [reading],
  relay_events: [{ id: 1, recorded_at: reading.recorded_at, relay_on: true, reason: "temperature_high", temperature_c: 19 }],
  settings: {
    db_path: "data.db", target_c: 18, cooling_on_c: 19, cooling_off_c: 18.5,
    notification_threshold_c: 20, interval_seconds: 5, camera_enabled: false,
    camera_stream_url: null, camera_device: "/dev/video0", camera_width: 640,
    camera_height: 480, camera_fps: 15, camera_jpeg_quality: 80
  }
};
