import type { ReactNode } from "react";

export function KpiCard({
  label,
  value,
  hint,
  tone
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "danger" | "warn" | "good";
}) {
  return (
    <div className={`kpi-card ${tone || ""}`}>
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      {hint ? <span className="kpi-hint">{hint}</span> : null}
    </div>
  );
}
