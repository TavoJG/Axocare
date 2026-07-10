import { onBeforeUnmount, onMounted, ref } from "vue";
import type { DashboardResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

export function useDashboard(fetcher: typeof fetch = fetch) {
  const spanMinutes = ref(60);
  const dashboard = ref<DashboardResponse | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const lastUpdated = ref<string | null>(null);
  let refreshTimer: number | undefined;
  let requestInFlight = false;

  function scheduleRefresh(intervalSeconds: number): void {
    window.clearTimeout(refreshTimer);
    refreshTimer = window.setTimeout(load, Math.max(intervalSeconds, 10) * 1000);
  }

  async function load(): Promise<void> {
    if (requestInFlight) return;
    requestInFlight = true;
    loading.value = true;
    error.value = null;

    try {
      const params = new URLSearchParams({
        span_minutes: String(spanMinutes.value),
        event_limit: "20"
      });
      const response = await fetcher(`${API_BASE}/api/dashboard?${params}`);
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      dashboard.value = (await response.json()) as DashboardResponse;
      lastUpdated.value = new Date().toISOString();
    } catch (reason) {
      error.value = reason instanceof Error ? reason.message : "Could not load dashboard data";
    } finally {
      requestInFlight = false;
      loading.value = false;
      scheduleRefresh(dashboard.value?.settings.interval_seconds ?? 10);
    }
  }

  function setSpan(minutes: number): void {
    spanMinutes.value = minutes;
    void load();
  }

  onMounted(load);
  onBeforeUnmount(() => window.clearTimeout(refreshTimer));

  return { spanMinutes, dashboard, loading, error, lastUpdated, load, setSpan };
}
