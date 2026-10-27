import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDate, formatFreshness, formatNumber } from "../lib/format";
import type { PipelineStatus } from "../lib/types";
import { Empty, ErrorBox, Loading } from "../components/Feedback";

const DAG_LABELS: Record<string, string> = {
  ingest_usgs: "Ingesta USGS",
  transform_quality: "Transformacion y calidad",
  backfill_usgs: "Backfill historico",
  daily_ai: "Reporte y anomalias IA"
};

export function Pipeline() {
  const { session } = useAuth();
  const [data, setData] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      setData(await apiFetch<PipelineStatus>("/api/pipeline/status"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo consultar el pipeline");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Estado del pipeline</h1>
          <p className="muted">
            Ultima ejecucion de cada DAG, compuerta de calidad y frescura de curated.
          </p>
        </div>
        <button className="btn" onClick={load}>
          Actualizar
        </button>
      </header>

      {error ? <ErrorBox message={error} onRetry={load} /> : null}
      {loading && !data ? <Loading /> : null}

      {data ? (
        <>
          <section className="kpi-grid compact">
            <div className="kpi-card">
              <span className="kpi-label">Frescura de curated</span>
              <span className="kpi-value">{formatFreshness(data.freshness_seconds)}</span>
              <span className="kpi-hint">{formatDate(data.last_update)}</span>
            </div>
            <div className="kpi-card">
              <span className="kpi-label">Calidad</span>
              <span className="kpi-value">
                {data.quality ? `${formatNumber(data.quality.score, 1)}%` : "Sin evaluar"}
              </span>
              <span className="kpi-hint">
                {data.quality
                  ? `${data.quality.passed}/${data.quality.total} aprobados`
                  : "Sin metricas"}
              </span>
            </div>
            <div className="kpi-card">
              <span className="kpi-label">Compuerta</span>
              <span className={`kpi-value ${data.quality?.gate_passed ? "good-text" : "danger-text"}`}>
                {data.quality?.gate_passed ? "APROBADA" : "NO APROBADA"}
              </span>
              <span className="kpi-hint">
                {data.quality ? formatDate(data.quality.checked_at) : "Sin dato"}
              </span>
            </div>
            <div className="kpi-card">
              <span className="kpi-label">Anomalias recientes</span>
              <span className="kpi-value">{data.anomalies.length}</span>
              <span className="kpi-hint">Metodo z-score por hora</span>
            </div>
          </section>

          <section className="dag-grid">
            {data.runs.length === 0 ? (
              <div className="panel">
                <Empty message="Aun no hay ejecuciones registradas. Lanza la ingesta desde Airflow." />
              </div>
            ) : (
              data.runs.map((run) => (
                <div key={run.dag_id} className="panel dag-card">
                  <div className="dag-header">
                    <h2>{DAG_LABELS[run.dag_id] || run.dag_id}</h2>
                    <span className={`tag ${run.status === "success" ? "good" : run.status === "failed" ? "danger" : "warn"}`}>
                      {run.status}
                    </span>
                  </div>
                  <p className="muted">{run.dag_id}</p>
                  <dl className="meta">
                    <div>
                      <dt>Inicio</dt>
                      <dd>{formatDate(run.started_at)}</dd>
                    </div>
                    <div>
                      <dt>Fin</dt>
                      <dd>{formatDate(run.finished_at)}</dd>
                    </div>
                    <div>
                      <dt>Run</dt>
                      <dd className="truncate">{run.run_id}</dd>
                    </div>
                  </dl>
                  {run.message ? <p className="message">{run.message}</p> : null}
                </div>
              ))
            )}
          </section>

          <section className="grid-two">
            <div className="panel">
              <div className="panel-title">
                <h2>Anomalias detectadas</h2>
                <span className="muted">Ventanas horarias</span>
              </div>
              {data.anomalies.length === 0 ? (
                <Empty message="Sin anomalias detectadas en el historico reciente." />
              ) : (
                <ul className="anomaly-list">
                  {data.anomalies.map((anomaly) => (
                    <li key={`${anomaly.window_start}-${anomaly.method}`}>
                      <div className="anomaly-head">
                        <span className={`tag ${anomaly.severity === "alta" ? "danger" : "warn"}`}>
                          {anomaly.severity}
                        </span>
                        <strong>{formatDate(anomaly.window_start)}</strong>
                        <span className="muted">
                          {anomaly.event_count} eventos · z {formatNumber(anomaly.score, 2)}
                        </span>
                      </div>
                      <p>{anomaly.explanation}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="panel">
              <div className="panel-title">
                <h2>Reglas de calidad</h2>
                <span className="muted">Ultima compuerta</span>
              </div>
              {data.quality ? (
                <>
                  <div className="quality-bar">
                    <div
                      className="quality-fill"
                      style={{ width: `${Math.min(100, data.quality.score)}%` }}
                    />
                  </div>
                  <p className="muted">
                    {data.quality.passed} aprobados · {data.quality.rejected} rechazados ·{" "}
                    {data.quality.total} evaluados
                  </p>
                  <dl className="meta">
                    <div>
                      <dt>Run</dt>
                      <dd className="truncate">{data.quality.dag_run_id}</dd>
                    </div>
                    <div>
                      <dt>Evaluado</dt>
                      <dd>{formatDate(data.quality.checked_at)}</dd>
                    </div>
                  </dl>
                  {session?.role === "admin" ? (
                    <details className="sql-box">
                      <summary>Detalle de reglas y rechazos</summary>
                      <pre>
                        {JSON.stringify(
                          { rules: data.quality.rules, details: data.quality.details },
                          null,
                          2
                        )}
                      </pre>
                    </details>
                  ) : null}
                </>
              ) : (
                <Empty message="Sin metricas de calidad registradas." />
              )}
            </div>
          </section>

          {session?.role === "admin" && data.run_history ? (
            <section className="panel">
              <div className="panel-title">
                <h2>Historial de ejecuciones</h2>
                <span className="muted">Solo administrador</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>DAG</th>
                      <th>Estado</th>
                      <th>Inicio</th>
                      <th>Fin</th>
                      <th>Mensaje</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.run_history.map((run, index) => (
                      <tr key={`${run.dag_id}-${run.run_id}-${index}`}>
                        <td>{run.dag_id}</td>
                        <td>
                          <span className={`tag ${run.status === "success" ? "good" : "danger"}`}>
                            {run.status}
                          </span>
                        </td>
                        <td>{formatDate(run.started_at)}</td>
                        <td>{formatDate(run.finished_at)}</td>
                        <td className="truncate">{run.message || ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
