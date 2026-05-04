import {
  Chart,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  CategoryScale
} from "chart.js";
import "./styles.css";

Chart.register(
  CategoryScale,
  Filler,
  Legend,
  LineController,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip
);

type TemperatureReading = {
  id: number;
  recorded_at: string;
  temperature_c: number | null;
  relay_on: boolean;
  sensor_id: string | null;
  error: string | null;
};

type RelayEvent = {
  id: number;
  recorded_at: string;
  relay_on: boolean;
  reason: string;
  temperature_c: number | null;
};

type ApiSettings = {
  db_path: string;
  target_c: number;
  cooling_on_c: number;
  cooling_off_c: number;
  interval_seconds: number;
};

type DashboardResponse = {
  db_path: string;
  settings: ApiSettings;
  current: TemperatureReading | null;
  readings: TemperatureReading[];
  relay_events: RelayEvent[];
  span_minutes: number;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "";
const SPAN_OPTIONS = [15, 30, 60, 180, 360, 720, 1440];
const state = {
  spanMinutes: 60,
  chart: null as Chart<"line", (number | null)[], string> | null,
  refreshTimer: 0
};

const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("App mount element not found");
}

app.innerHTML = `
  <div class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">Aquarium controller</p>
        <h1>Axocare</h1>
      </div>
      <div class="toolbar">
        <label class="field">
          <span>Time span</span>
          <select id="spanSelect">
            ${SPAN_OPTIONS.map(
              (minutes) => `<option value="${minutes}">${formatSpan(minutes)}</option>`
            ).join("")}
          </select>
        </label>
        <button id="refreshButton" type="button">Refresh</button>
      </div>
    </header>

    <main>
      <section id="status" class="status-grid" aria-live="polite"></section>

      <section class="panel chart-panel">
        <div class="panel-header">
          <div>
            <p class="eyebrow">Temperature history</p>
            <h2 id="chartTitle">Last hour</h2>
          </div>
          <p id="lastUpdated" class="muted"></p>
        </div>
        <div class="chart-frame">
          <div id="chartEmpty" class="empty" hidden>No readings found for this time span.</div>
          <canvas id="temperatureChart" aria-label="Temperature history chart"></canvas>
        </div>
      </section>

      <section class="split">
        <div class="panel">
          <div class="panel-header">
            <div>
              <p class="eyebrow">Recent readings</p>
              <h2>Sensor log</h2>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Temperature</th>
                  <th>Relay</th>
                  <th>Sensor</th>
                </tr>
              </thead>
              <tbody id="readingsBody"></tbody>
            </table>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <div>
              <p class="eyebrow">Relay events</p>
              <h2>Cooling activity</h2>
            </div>
          </div>
          <div id="eventsList" class="events"></div>
        </div>
      </section>
    </main>
  </div>
`;

const spanSelect = document.querySelector<HTMLSelectElement>("#spanSelect")!;
const refreshButton = document.querySelector<HTMLButtonElement>("#refreshButton")!;
const status = document.querySelector<HTMLElement>("#status")!;
const chartTitle = document.querySelector<HTMLElement>("#chartTitle")!;
const chartEmpty = document.querySelector<HTMLElement>("#chartEmpty")!;
const lastUpdated = document.querySelector<HTMLElement>("#lastUpdated")!;
const readingsBody = document.querySelector<HTMLTableSectionElement>("#readingsBody")!;
const eventsList = document.querySelector<HTMLElement>("#eventsList")!;
const chartCanvas = document.querySelector<HTMLCanvasElement>("#temperatureChart")!;

spanSelect.value = String(state.spanMinutes);
spanSelect.addEventListener("change", () => {
  state.spanMinutes = Number(spanSelect.value);
  loadDashboard();
});
refreshButton.addEventListener("click", () => loadDashboard());

loadDashboard();

async function loadDashboard(): Promise<void> {
  setBusy(true);

  try {
    const params = new URLSearchParams({
      span_minutes: String(state.spanMinutes),
      event_limit: "20"
    });
    const response = await fetch(`${API_BASE}/api/dashboard?${params.toString()}`);

    if (!response.ok) {
      throw new Error(`API returned ${response.status}`);
    }

    const payload = (await response.json()) as DashboardResponse;
    renderDashboard(payload);
    scheduleRefresh(payload.settings.interval_seconds);
  } catch (error) {
    renderError(error instanceof Error ? error.message : "Could not load dashboard data");
  } finally {
    setBusy(false);
  }
}

function renderDashboard(payload: DashboardResponse): void {
  renderStatus(payload);
  renderChart(payload);
  renderReadings(payload.readings);
  renderEvents(payload.relay_events);
  chartTitle.textContent = `Last ${formatSpan(payload.span_minutes).toLowerCase()}`;
  lastUpdated.textContent = `Updated ${formatTime(new Date().toISOString())}`;
}

function renderStatus(payload: DashboardResponse): void {
  const current = payload.current;
  const settings = payload.settings;
  const relayOn = current?.relay_on ?? false;
  const sensorState = current?.error ? "Error" : current ? "OK" : "No data";

  status.innerHTML = `
    ${metricCard("Current temperature", formatTemperature(current?.temperature_c), current?.error ? "danger" : "")}
    ${metricCard("Relay", relayOn ? "On" : "Off", relayOn ? "active" : "")}
    ${metricCard("Sensor", sensorState, current?.error ? "danger" : "")}
    ${metricCard("Target", formatTemperature(settings.target_c), "")}
    ${metricCard("Cooling on", formatTemperature(settings.cooling_on_c), "")}
    ${metricCard("Cooling off", formatTemperature(settings.cooling_off_c), "")}
  `;

  if (current?.error) {
    status.insertAdjacentHTML(
      "beforeend",
      `<article class="metric metric-wide danger"><span>Sensor message</span><strong>${escapeHtml(current.error)}</strong></article>`
    );
  }
}

function renderChart(payload: DashboardResponse): void {
  const labels = payload.readings.map((reading) => formatTime(reading.recorded_at));
  const temperatures = payload.readings.map((reading) => reading.temperature_c);
  const target = payload.readings.map(() => payload.settings.target_c);
  const coolingOn = payload.readings.map(() => payload.settings.cooling_on_c);
  const coolingOff = payload.readings.map(() => payload.settings.cooling_off_c);

  chartEmpty.hidden = payload.readings.length > 0;
  chartCanvas.hidden = payload.readings.length === 0;

  if (payload.readings.length === 0) {
    state.chart?.destroy();
    state.chart = null;
    return;
  }

  if (state.chart) {
    state.chart.data.labels = labels;
    state.chart.data.datasets[0].data = temperatures;
    state.chart.data.datasets[1].data = target;
    state.chart.data.datasets[2].data = coolingOn;
    state.chart.data.datasets[3].data = coolingOff;
    state.chart.update();
    return;
  }

  state.chart = new Chart(chartCanvas, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Temperature C",
          data: temperatures,
          borderColor: "#0f766e",
          backgroundColor: "rgba(15, 118, 110, 0.12)",
          fill: true,
          tension: 0.3,
          pointRadius: 2,
          pointHoverRadius: 5,
          spanGaps: false
        },
        thresholdDataset("Target", target, "#2563eb"),
        thresholdDataset("Cooling on", coolingOn, "#dc2626"),
        thresholdDataset("Cooling off", coolingOff, "#f59e0b")
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: "index"
      },
      plugins: {
        legend: {
          labels: {
            boxWidth: 12,
            color: "#24323a",
            usePointStyle: true
          }
        },
        tooltip: {
          callbacks: {
            label(context) {
              const value = context.parsed.y;
              return `${context.dataset.label}: ${value != null && Number.isFinite(value) ? value.toFixed(2) : "No data"} C`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: {
            color: "rgba(36, 50, 58, 0.08)"
          },
          ticks: {
            autoSkip: true,
            maxTicksLimit: 8,
            color: "#5f6f76"
          }
        },
        y: {
          grid: {
            color: "rgba(36, 50, 58, 0.08)"
          },
          ticks: {
            color: "#5f6f76",
            callback: (value) => `${value} C`
          }
        }
      }
    }
  });
}

function renderReadings(readings: TemperatureReading[]): void {
  const rows = readings.slice(-12).reverse();

  readingsBody.innerHTML =
    rows.length === 0
      ? `<tr><td colspan="4" class="muted">No readings recorded.</td></tr>`
      : rows
          .map(
            (reading) => `
        <tr>
          <td>${formatTime(reading.recorded_at)}</td>
          <td>${formatTemperature(reading.temperature_c)}</td>
          <td><span class="pill ${reading.relay_on ? "on" : ""}">${reading.relay_on ? "On" : "Off"}</span></td>
          <td>${reading.error ? `<span class="text-danger">${escapeHtml(reading.error)}</span>` : escapeHtml(reading.sensor_id ?? "OK")}</td>
        </tr>
      `
          )
          .join("");
}

function renderEvents(events: RelayEvent[]): void {
  eventsList.innerHTML =
    events.length === 0
      ? `<div class="empty compact">No relay events recorded.</div>`
      : events
          .map(
            (event) => `
        <article class="event">
          <div>
            <strong>${event.relay_on ? "Relay on" : "Relay off"}</strong>
            <span>${escapeHtml(event.reason.replace(/_/g, " "))}</span>
          </div>
          <div class="event-meta">
            <span>${formatTemperature(event.temperature_c)}</span>
            <time>${formatTime(event.recorded_at)}</time>
          </div>
        </article>
      `
          )
          .join("");
}

function renderError(message: string): void {
  status.innerHTML = `
    <article class="metric metric-wide danger">
      <span>Dashboard unavailable</span>
      <strong>${escapeHtml(message)}</strong>
    </article>
  `;
}

function setBusy(isBusy: boolean): void {
  refreshButton.disabled = isBusy;
  refreshButton.textContent = isBusy ? "Refreshing" : "Refresh";
}

function scheduleRefresh(intervalSeconds: number): void {
  window.clearTimeout(state.refreshTimer);
  state.refreshTimer = window.setTimeout(
    () => loadDashboard(),
    Math.max(intervalSeconds, 10) * 1000
  );
}

function thresholdDataset(label: string, data: number[], color: string) {
  return {
    label,
    data,
    borderColor: color,
    borderDash: [6, 6],
    borderWidth: 1.5,
    pointRadius: 0,
    tension: 0
  };
}

function metricCard(label: string, value: string, tone: string): string {
  return `<article class="metric ${tone}"><span>${label}</span><strong>${escapeHtml(value)}</strong></article>`;
}

function formatTemperature(value: number | null | undefined): string {
  return value == null ? "No data" : `${value.toFixed(2)} C`;
}

function formatSpan(minutes: number): string {
  if (minutes < 60) {
    return `${minutes} min`;
  }
  if (minutes === 60) {
    return "1 hour";
  }
  if (minutes < 1440) {
    return `${minutes / 60} hours`;
  }
  return "24 hours";
}

function formatTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => {
    const entities: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    };
    return entities[char];
  });
}
