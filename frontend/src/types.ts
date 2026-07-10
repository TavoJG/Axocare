export type TemperatureReading = {
  id: number;
  recorded_at: string;
  temperature_c: number | null;
  relay_on: boolean;
  sensor_id: string | null;
  error: string | null;
  room_temperature: number | null;
  aht20_humidity_percent: number | null;
  bmp280_temperature_c: number | null;
  bmp280_pressure_hpa: number | null;
  ambient_error: string | null;
};

export type RelayEvent = {
  id: number;
  recorded_at: string;
  relay_on: boolean;
  reason: string;
  temperature_c: number | null;
};

export type ApiSettings = {
  db_path: string;
  target_c: number;
  cooling_on_c: number;
  cooling_off_c: number;
  notification_threshold_c: number | null;
  interval_seconds: number;
  camera_enabled: boolean;
  camera_stream_url: string | null;
  camera_device: string;
  camera_width: number;
  camera_height: number;
  camera_fps: number;
  camera_jpeg_quality: number;
};

export type DashboardResponse = {
  db_path: string;
  settings: ApiSettings;
  current: TemperatureReading | null;
  readings: TemperatureReading[];
  relay_events: RelayEvent[];
  span_minutes: number;
};

export type AgentChatMessage = {
  role: "user" | "assistant";
  content: string;
};
