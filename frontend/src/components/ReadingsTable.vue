<script setup lang="ts">
import { computed, ref } from "vue";
import { formatPercent, formatPressure, formatTemperature, formatTime, sensorMessages } from "../formatters";
import type { TemperatureReading } from "../types";
const props = defineProps<{ readings: TemperatureReading[] }>();
const rows = computed(() => props.readings.slice(-12).reverse());
const collapsed = ref(true);
</script>
<template><div class="panel"><div class="panel-header"><div><p class="eyebrow">Recent readings</p><h2>Sensor log</h2></div><button type="button" class="button-secondary button-small collapse-toggle" :aria-expanded="!collapsed" @click="collapsed = !collapsed">{{ collapsed ? "Expand" : "Collapse" }}</button></div><div v-if="!collapsed" class="table-wrap"><table><thead><tr><th>Time</th><th>Tank Temp</th><th>Room Temp</th><th>Humidity</th><th>BMP280 Temp</th><th>Pressure</th><th>Relay</th><th>Sensor</th></tr></thead><tbody><tr v-if="!rows.length"><td colspan="8" class="muted">No readings recorded.</td></tr><tr v-for="reading in rows" :key="reading.id"><td><time :datetime="reading.recorded_at">{{ formatTime(reading.recorded_at) }}</time></td><td>{{ formatTemperature(reading.temperature_c) }}</td><td>{{ formatTemperature(reading.room_temperature, 1) }}</td><td>{{ formatPercent(reading.aht20_humidity_percent) }}</td><td>{{ formatTemperature(reading.bmp280_temperature_c) }}</td><td>{{ formatPressure(reading.bmp280_pressure_hpa) }}</td><td><span class="pill" :class="{ on: reading.relay_on }">{{ reading.relay_on ? "On" : "Off" }}</span></td><td :class="{ 'text-danger': sensorMessages(reading).length }">{{ sensorMessages(reading).join(" | ") || reading.sensor_id || "OK" }}</td></tr></tbody></table></div></div></template>
