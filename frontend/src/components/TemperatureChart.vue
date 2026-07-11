<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Chart, thresholdDataset } from "../chart";
import { getChartPalette } from "../chartTheme";
import { formatTime } from "../formatters";
import type { DashboardResponse } from "../types";

const props = defineProps<{ payload: DashboardResponse; themeKey: string; title: string; lastUpdated: string }>();
const canvas = ref<HTMLCanvasElement>();
let chart: Chart<"line", (number | null)[], string> | null = null;

function render(): void {
  const readings = props.payload.readings;
  if (!readings.length || !canvas.value) { chart?.destroy(); chart = null; return; }
  const palette = getChartPalette();
  const labels = readings.map((item) => formatTime(item.recorded_at));
  const threshold = props.payload.settings.notification_threshold_c;
  const datasets = [
    { label: "Tank temperature", data: readings.map((item) => item.temperature_c), borderColor: palette.accent, backgroundColor: palette.accentFill, fill: true, tension: 0.3, pointRadius: 2, pointHoverRadius: 5, spanGaps: false },
    thresholdDataset("Target", readings.map(() => props.payload.settings.target_c), palette.info),
    thresholdDataset("Cooling on", readings.map(() => props.payload.settings.cooling_on_c), palette.danger),
    thresholdDataset("Cooling off", readings.map(() => props.payload.settings.cooling_off_c), palette.warning),
    ...(threshold == null ? [] : [thresholdDataset("Notify above", readings.map(() => threshold), palette.secondary)])
  ];
  const options = {
    responsive: true, maintainAspectRatio: false, interaction: { intersect: false, mode: "index" as const },
    plugins: { legend: { labels: { boxWidth: 12, color: palette.legend, usePointStyle: true } }, tooltip: { callbacks: { label(context: { parsed: { y: number | null }; dataset: { label?: string } }) { const value = context.parsed.y; return `${context.dataset.label}: ${value != null && Number.isFinite(value) ? value.toFixed(2) : "No data"} C`; } } } },
    scales: { x: { grid: { color: palette.grid }, ticks: { autoSkip: true, maxTicksLimit: 8, color: palette.axis } }, y: { grid: { color: palette.grid }, ticks: { color: palette.axis, callback: (value: string | number) => `${value} C` } } }
  };
  if (chart) { chart.data.labels = labels; chart.data.datasets = datasets; chart.options = options; chart.update(); return; }
  chart = new Chart(canvas.value, { type: "line", data: { labels, datasets }, options });
}
watch(() => [props.payload, props.themeKey], () => nextTick(render), { deep: true });
onMounted(render);
onBeforeUnmount(() => chart?.destroy());
</script>

<template><section class="panel chart-panel"><div class="panel-header"><div><p class="eyebrow">Temperature history</p><h2>{{ title }}</h2></div><p class="muted">{{ lastUpdated }}</p></div><div class="chart-frame"><div v-if="!payload.readings.length" class="empty">No readings found for this time span.</div><canvas v-show="payload.readings.length" ref="canvas" aria-label="Temperature history chart"></canvas></div></section></template>
