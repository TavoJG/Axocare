<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Chart } from "../chart";
import { getChartPalette } from "../chartTheme";
import { formatTemperature, formatTime } from "../formatters";
import type { DashboardResponse } from "../types";

const props = defineProps<{ payload: DashboardResponse; themeKey: string; title: string }>();
const canvas = ref<HTMLCanvasElement>();
let chart: Chart<"line", (number | null)[], string> | null = null;
function render(): void {
  const readings = props.payload.readings;
  if (!readings.length || !canvas.value) { chart?.destroy(); chart = null; return; }
  const palette = getChartPalette();
  const labels = readings.map((item) => formatTime(item.recorded_at));
  const datasets = [
    { label: "Relative humidity", data: readings.map((item) => item.aht20_humidity_percent), borderColor: palette.accent, backgroundColor: palette.accentFill, fill: true, tension: 0.3, pointRadius: 2, pointHoverRadius: 5, spanGaps: false },
    { label: "Room temperature", data: readings.map((item) => item.room_temperature), borderColor: palette.info, backgroundColor: palette.secondaryFill, fill: false, tension: 0.3, pointRadius: 2, pointHoverRadius: 5, spanGaps: false, yAxisID: "yTemp" }
  ];
  const options = {
    responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: "index" as const },
    plugins: { legend: { labels: { boxWidth: 12, color: palette.legend, usePointStyle: true } }, tooltip: { callbacks: { label(context: { parsed: { y: number | null }; dataset: { label?: string; yAxisID?: string } }) { const value = context.parsed.y; return context.dataset.yAxisID === "yTemp" ? `${context.dataset.label}: ${formatTemperature(value, 1)}` : `${context.dataset.label}: ${value != null && Number.isFinite(value) ? value.toFixed(1) : "No data"} %`; } } } },
    scales: { x: { grid: { color: palette.grid }, ticks: { autoSkip: true, maxTicksLimit: 8, color: palette.axis } }, y: { grid: { color: palette.grid }, ticks: { color: palette.axis, callback: (value: string | number) => `${value} %` } }, yTemp: { position: "right" as const, grid: { drawOnChartArea: false }, ticks: { color: palette.info, callback: (value: string | number) => `${value} C` } } }
  };
  if (chart) { chart.data.labels = labels; chart.data.datasets = datasets; chart.options = options; chart.update(); return; }
  chart = new Chart(canvas.value, { type: "line", data: { labels, datasets }, options });
}
watch(() => [props.payload, props.themeKey], () => nextTick(render), { deep: true });
onMounted(render);
onBeforeUnmount(() => chart?.destroy());
</script>

<template><section class="panel chart-panel"><div class="panel-header"><div><p class="eyebrow">Ambient humidity</p><h2>{{ title }}</h2></div></div><div class="chart-frame"><div v-if="!payload.readings.length" class="empty">No humidity readings found for this time span.</div><canvas v-show="payload.readings.length" ref="canvas" aria-label="Relative humidity history chart"></canvas></div></section></template>
