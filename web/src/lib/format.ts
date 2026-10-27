export function formatDate(value: string | null | undefined): string {
  if (!value) return "Sin dato";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("es-CO", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "Sin dato";
  return value.toLocaleString("es-CO", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
}

export function formatFreshness(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "Sin datos";
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)} h`;
  return `${(seconds / 86400).toFixed(1)} dias`;
}

export function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 12)}...` : value;
}
