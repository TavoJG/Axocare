<script setup lang="ts">
import { computed } from "vue";
import { formatPercent, formatPressure, formatTemperature } from "../formatters";
import type { DashboardResponse } from "../types";

const props = defineProps<{ payload: DashboardResponse }>();
const cards = computed(() => {
  const current = props.payload.current;
  const settings = props.payload.settings;
  const relayOn = current?.relay_on ?? false;
  return [
    ["Current temperature", formatTemperature(current?.temperature_c), current?.error ? "danger" : ""],
    ["Humidity", formatPercent(current?.aht20_humidity_percent), current?.ambient_error ? "danger" : ""],
    ["Pressure", formatPressure(current?.bmp280_pressure_hpa), current?.ambient_error ? "danger" : ""],
    ["Relay", relayOn ? "On" : "Off", relayOn ? "active" : ""],
    ["Sensor", current?.error ? "Error" : current ? "OK" : "No data", current?.error ? "danger" : ""],
    ["Target", formatTemperature(settings.target_c), ""],
    ["Cooling on", formatTemperature(settings.cooling_on_c), ""],
    ["Cooling off", formatTemperature(settings.cooling_off_c), ""],
    ["Notify above", formatTemperature(settings.notification_threshold_c), ""]
  ];
});
</script>

<template>
  <section class="status-grid" aria-live="polite">
    <article v-for="card in cards" :key="card[0]" class="metric" :class="card[2]"><span>{{ card[0] }}</span><strong>{{ card[1] }}</strong></article>
    <article v-if="payload.current?.error" class="metric metric-wide danger"><span>Sensor message</span><strong>{{ payload.current.error }}</strong></article>
    <article v-if="payload.current?.ambient_error" class="metric metric-wide danger"><span>I2C sensor message</span><strong>{{ payload.current.ambient_error }}</strong></article>
  </section>
</template>
