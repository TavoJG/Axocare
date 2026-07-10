<script setup lang="ts">
import { computed } from "vue";
import CameraPanel from "./components/CameraPanel.vue";
import AgentChat from "./components/AgentChat.vue";
import HumidityChart from "./components/HumidityChart.vue";
import ReadingsTable from "./components/ReadingsTable.vue";
import RelayEvents from "./components/RelayEvents.vue";
import StatusGrid from "./components/StatusGrid.vue";
import TemperatureChart from "./components/TemperatureChart.vue";
import { formatSpan, formatTime } from "./formatters";
import { useDashboard } from "./useDashboard";

const SPAN_OPTIONS = [15, 30, 60, 180, 360, 720, 1440];
const { spanMinutes, dashboard, loading, error, lastUpdated, load, setSpan } = useDashboard();
const title = computed(() => `Last ${formatSpan(dashboard.value?.span_minutes ?? spanMinutes.value).toLowerCase()}`);
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div><p class="eyebrow">Aquarium controller</p><h1>Axocare</h1></div>
      <div class="toolbar">
        <label class="field"><span>Time span</span>
          <select :value="spanMinutes" @change="setSpan(Number(($event.target as HTMLSelectElement).value))">
            <option v-for="minutes in SPAN_OPTIONS" :key="minutes" :value="minutes">{{ formatSpan(minutes) }}</option>
          </select>
        </label>
        <button type="button" :disabled="loading" @click="load">{{ loading ? "Refreshing" : "Refresh" }}</button>
      </div>
    </header>

    <main>
      <div v-if="error" class="dashboard-alert" role="alert">
        <strong>Dashboard unavailable</strong><span>{{ error }}</span>
      </div>
      <StatusGrid v-if="dashboard" :payload="dashboard" />
      <section v-else-if="loading" class="status-grid" aria-live="polite">
        <article class="metric metric-wide"><span>Dashboard</span><strong>Loading…</strong></article>
      </section>

      <template v-if="dashboard">
        <AgentChat />
        <CameraPanel :settings="dashboard.settings" />
        <TemperatureChart :payload="dashboard" :title="title" :last-updated="lastUpdated ? `Updated ${formatTime(lastUpdated)}` : ''" />
        <HumidityChart :payload="dashboard" :title="title" />
        <section class="split">
          <ReadingsTable :readings="dashboard.readings" />
          <RelayEvents :events="dashboard.relay_events" />
        </section>
      </template>
    </main>
  </div>
</template>
