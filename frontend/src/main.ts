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
  aht20_temperature_c: number | null;
  aht20_humidity_percent: number | null;
  bmp280_temperature_c: number | null;
  bmp280_pressure_hpa: number | null;
  ambient_error: string | null;
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
  notification_threshold_c: number | null;
  interval_seconds: number;
  camera_enabled: boolean;
  camera_device: string;
  camera_width: number;
  camera_height: number;
  camera_fps: number;
  camera_jpeg_quality: number;
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
  refreshTimer: 0,
  cameraRetryTimer: 0,
  cameraRetryCount: 0
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

      <section id="cameraPanel" class="panel camera-panel" hidden>
        <div class="panel-header">
          <div>
            <p class="eyebrow">Live camera</p>
            <h2>Tank view</h2>
          </div>
          <span id="cameraMeta" class="muted"></span>
        </div>
        <div class="camera-frame">
          <div id="cameraError" class="camera-error" hidden>Camera stream unavailable</div>
          <img id="cameraStream" alt="Live aquarium camera stream" />
        </div>
      </section>

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
                  <th>Tank Temp</th>
                  <th>AHT20 Temp</th>
                  <th>Humidity</th>
                  <th>BMP280 Temp</th>
                  <th>Pressure</th>
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
const cameraPanel = document.querySelector<HTMLElement>("#cameraPanel")!;
const cameraMeta = document.querySelector<HTMLElement>("#cameraMeta")!;
const cameraStream = document.querySelector<HTMLImageElement>("#cameraStream")!;
const cameraError = document.querySelector<HTMLElement>("#cameraError")!;

spanSelect.value = String(state.spanMinutes);
spanSelect.addEventListener("change", () => {
  state.spanMinutes = Number(spanSelect.value);
  loadDashboard();
});
refreshButton.addEventListener("click", () => loadDashboard());
cameraStream.addEventListener("load", () => {
  window.clearTimeout(state.cameraRetryTimer);
  state.cameraRetryCount = 0;
  cameraError.hidden = true;
  cameraStream.hidden = false;
});
cameraStream.addEventListener("error", () => {
  cameraError.hidden = false;
  cameraStream.hidden = true;
  scheduleCameraRetry();
});
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && !cameraPanel.hidden) {
    startCameraStream();
  }
});

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
  renderCamera(payload.settings);
  renderChart(payload);
  renderReadings(payload.readings);
  renderEvents(payload.relay_events);
  chartTitle.textContent = `Last ${formatSpan(payload.span_minutes).toLowerCase()}`;
  lastUpdated.textContent = `Updated ${formatTime(new Date().toISOString())}`;
}

function renderCamera(settings: ApiSettings): void {
  cameraPanel.hidden = !settings.camera_enabled;
  if (!settings.camera_enabled) {
    cameraStream.removeAttribute("src");
    cameraError.hidden = true;
    return;
  }

  cameraMeta.textContent = `${settings.camera_width}x${settings.camera_height} at ${settings.camera_fps} fps`;
  if (!cameraStream.src) {
    startCameraStream();
  }
}

function startCameraStream(): void {
  window.clearTimeout(state.cameraRetryTimer);
  cameraError.hidden = true;
  cameraStream.hidden = false;
  cameraStream.src = `${API_BASE}/api/camera/stream?t=${Date.now()}`;
}

function scheduleCameraRetry(): void {
  window.clearTimeout(state.cameraRetryTimer);
  const delayMs = Math.min(1000 * 2 ** state.cameraRetryCount, 15000);
  state.cameraRetryCount += 1;
  state.cameraRetryTimer = window.setTimeout(() => {
    if (!cameraPanel.hidden && !document.hidden) {
      startCameraStream();
    }
  }, delayMs);
}

function renderStatus(payload: DashboardResponse): void {
  const current = payload.current;
  const settings = payload.settings;
  const relayOn = current?.relay_on ?? false;
  const sensorState = current?.error ? "Error" : current ? "OK" : "No data";

  status.innerHTML = `
    ${metricCard("Current temperature", formatTemperature(current?.temperature_c), current?.error ? "danger" : "")}
    ${metricCard("Humidity", formatPercent(current?.aht20_humidity_percent), current?.ambient_error ? "danger" : "")}
    ${metricCard("Pressure", formatPressure(current?.bmp280_pressure_hpa), current?.ambient_error ? "danger" : "")}
    ${metricCard("Relay", relayOn ? "On" : "Off", relayOn ? "active" : "")}
    ${metricCard("Sensor", sensorState, current?.error ? "danger" : "")}
    ${metricCard("Target", formatTemperature(settings.target_c), "")}
    ${metricCard("Cooling on", formatTemperature(settings.cooling_on_c), "")}
    ${metricCard("Cooling off", formatTemperature(settings.cooling_off_c), "")}
    ${metricCard("Notify above", formatTemperature(settings.notification_threshold_c), "")}
  `;

  if (current?.error) {
    status.insertAdjacentHTML(
      "beforeend",
      `<article class="metric metric-wide danger"><span>Sensor message</span><strong>${escapeHtml(current.error)}</strong></article>`
    );
  }

  if (current?.ambient_error) {
    status.insertAdjacentHTML(
      "beforeend",
      `<article class="metric metric-wide danger"><span>I2C sensor message</span><strong>${escapeHtml(current.ambient_error)}</strong></article>`
    );
  }
}

function renderChart(payload: DashboardResponse): void {
  const labels = payload.readings.map((reading) => formatTime(reading.recorded_at));
  const temperatures = payload.readings.map((reading) => reading.temperature_c);
  const target = payload.readings.map(() => payload.settings.target_c);
  const coolingOn = payload.readings.map(() => payload.settings.cooling_on_c);
  const coolingOff = payload.readings.map(() => payload.settings.cooling_off_c);
  const threshold = payload.settings.notification_threshold_c;
  const notificationThreshold =
    threshold == null
      ? null
      : payload.readings.map(() => threshold);

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
    if (notificationThreshold == null) {
      state.chart.data.datasets = state.chart.data.datasets.slice(0, 4);
    } else if (state.chart.data.datasets[4]) {
      state.chart.data.datasets[4].data = notificationThreshold;
    } else {
      state.chart.data.datasets.push(
        thresholdDataset("Notify above", notificationThreshold, "#7c3aed")
      );
    }
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
        thresholdDataset("Cooling off", coolingOff, "#f59e0b"),
        ...(notificationThreshold == null
          ? []
          : [thresholdDataset("Notify above", notificationThreshold, "#7c3aed")])
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
      ? `<tr><td colspan="8" class="muted">No readings recorded.</td></tr>`
      : rows
          .map(
            (reading) => `
        <tr>
          <td>${formatTime(reading.recorded_at)}</td>
          <td>${formatTemperature(reading.temperature_c)}</td>
          <td>${formatTemperature(reading.aht20_temperature_c)}</td>
          <td>${formatPercent(reading.aht20_humidity_percent)}</td>
          <td>${formatTemperature(reading.bmp280_temperature_c)}</td>
          <td>${formatPressure(reading.bmp280_pressure_hpa)}</td>
          <td><span class="pill ${reading.relay_on ? "on" : ""}">${reading.relay_on ? "On" : "Off"}</span></td>
          <td>${formatSensorState(reading)}</td>
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

function formatPercent(value: number | null | undefined): string {
  return value == null ? "No data" : `${value.toFixed(1)} %`;
}

function formatPressure(value: number | null | undefined): string {
  return value == null ? "No data" : `${value.toFixed(1)} hPa`;
}

function formatSensorState(reading: TemperatureReading): string {
  const messages = [reading.error, reading.ambient_error].filter(
    (message): message is string => Boolean(message)
  );

  if (messages.length > 0) {
    return `<span class="text-danger">${escapeHtml(messages.join(" | "))}</span>`;
  }

  return escapeHtml(reading.sensor_id ?? "OK");
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
