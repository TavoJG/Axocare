import {
  CategoryScale, Chart, Filler, Legend, LineController, LineElement,
  LinearScale, PointElement, Tooltip
} from "chart.js";

Chart.register(CategoryScale, Filler, Legend, LineController, LineElement, LinearScale, PointElement, Tooltip);

export function thresholdDataset(label: string, data: number[], color: string) {
  return { label, data, borderColor: color, borderDash: [6, 6], borderWidth: 1.5, pointRadius: 0, tension: 0 };
}

export { Chart };
