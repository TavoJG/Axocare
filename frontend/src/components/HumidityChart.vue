<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Chart } from "../chart";
import { formatTime } from "../formatters";
import type { DashboardResponse } from "../types";

const props = defineProps<{ payload: DashboardResponse; title: string }>();
const canvas = ref<HTMLCanvasElement>();
let chart: Chart<"line", (number | null)[], string> | null = null;
function render(): void {
  const readings = props.payload.readings;
  if (!readings.length || !canvas.value) { chart?.destroy(); chart = null; return; }
  const labels = readings.map((item) => formatTime(item.recorded_at));
  const datasets = [
    { label: "Relative humidity", data: readings.map((item) => item.aht20_humidity_percent), borderColor: "#0f766e", backgroundColor: "rgba(15, 118, 110, 0.12)", fill: true, tension: 0.3, pointRadius: 2, pointHoverRadius: 5, spanGaps: false },
    { label: "Room temperature", data: readings.map((item) => item.room_temperature), borderColor: "#1d4ed8", backgroundColor: "rgba(29, 78, 216, 0.08)", fill: false, tension: 0.3, pointRadius: 2, pointHoverRadius: 5, spanGaps: false, yAxisID: "yTemp" }
  ];
  if (chart) { chart.data.labels = labels; chart.data.datasets = datasets; chart.update(); return; }
  chart = new Chart(canvas.value, { type: "line", data: { labels, datasets }, options: {
    responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: "index" },
    plugins: { legend: { labels: { boxWidth: 12, color: "#24323a", usePointStyle: true } }, tooltip: { callbacks: { label(context) { const value = context.parsed.y; const unit = context.dataset.yAxisID === "yTemp" ? "C" : "%"; const digits = unit === "C" ? 2 : 1; return `${context.dataset.label}: ${value != null && Number.isFinite(value) ? value.toFixed(digits) : "No data"} ${unit}`; } } } },
    scales: { x: { grid: { color: "rgba(36, 50, 58, 0.08)" }, ticks: { autoSkip: true, maxTicksLimit: 8, color: "#5f6f76" } }, y: { grid: { color: "rgba(36, 50, 58, 0.08)" }, ticks: { color: "#5f6f76", callback: (value) => `${value} %` } }, yTemp: { position: "right", grid: { drawOnChartArea: false }, ticks: { color: "#1d4ed8", callback: (value) => `${value} C` } } }
  } });
}
watch(() => props.payload, () => nextTick(render), { deep: true });
onMounted(render);
onBeforeUnmount(() => chart?.destroy());
</script>

<template><section class="panel chart-panel"><div class="panel-header"><div><p class="eyebrow">Ambient humidity</p><h2>{{ title }}</h2></div></div><div class="chart-frame"><div v-if="!payload.readings.length" class="empty">No humidity readings found for this time span.</div><canvas v-show="payload.readings.length" ref="canvas" aria-label="Relative humidity history chart"></canvas></div></section></template>
