export type ChartPalette = {
  accent: string;
  accentFill: string;
  axis: string;
  danger: string;
  info: string;
  grid: string;
  legend: string;
  secondary: string;
  secondaryFill: string;
  warning: string;
};

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function getChartPalette(): ChartPalette {
  return {
    accent: cssVar("--color-accent"),
    accentFill: cssVar("--color-accent-soft"),
    axis: cssVar("--color-text-soft"),
    danger: cssVar("--color-danger-strong"),
    info: cssVar("--color-info"),
    grid: cssVar("--color-chart-grid"),
    legend: cssVar("--color-text"),
    secondary: cssVar("--color-chart-secondary"),
    secondaryFill: cssVar("--color-chart-secondary-soft"),
    warning: cssVar("--color-warning")
  };
}
