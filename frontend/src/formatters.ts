import type { TemperatureReading } from "./types";

export function formatTemperature(value: number | null | undefined): string {
  return value == null ? "No data" : `${value.toFixed(2)} C`;
}

export function formatPercent(value: number | null | undefined): string {
  return value == null ? "No data" : `${value.toFixed(1)} %`;
}

export function formatPressure(value: number | null | undefined): string {
  return value == null ? "No data" : `${value.toFixed(1)} hPa`;
}

export function sensorMessages(reading: TemperatureReading): string[] {
  return [reading.error, reading.ambient_error].filter(
    (message): message is string => Boolean(message)
  );
}

export function formatSpan(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  if (minutes === 60) return "1 hour";
  if (minutes < 1440) return `${minutes / 60} hours`;
  return "24 hours";
}

export function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}
