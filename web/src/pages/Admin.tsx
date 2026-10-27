import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDate, formatNumber } from "../lib/format";
import type { AiRun } from "../lib/types";
import { Empty, ErrorBox, Loading } from "../components/Feedback";

export function Admin() {
  const { session } = useAuth();
  const [runs, setRuns] = useState<AiRun[]>([]);
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [working, setWorking] = useState("");

  async function loadRuns() {
    try {
      setRuns(await apiFetch<AiRun[]>("/api/admin/ai-runs?limit=20"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar las ejecuciones IA");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (session?.role !== "admin") {
      setLoading(false);
      return;
    }
    loadRuns();
  }, [session]);

  if (session?.role !== "admin") {
    return (
      <div className="page">
        <div className="panel">
          <h1>Acceso restringido</h1>
          <p className="muted">
            Esta seccion requiere rol administrador. El backend tambien rechaza la llamada
            directa con 403.
          </p>
        </div>
      </div>
    );
  }

  async function launchBackfill() {
    setWorking("backfill");
    setError("");
    setNotice("");
    try {
      const result = await apiFetch<{ dag_run_id: string; state: string }>(
        "/api/admin/backfill",
        { method: "POST", body: JSON.stringify({ days }) }
      );
      setNotice(`Backfill lanzado: ${result.dag_run_id} (estado ${result.state})`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo lanzar el backfill");
    } finally {
      setWorking("");
    }
  }

  async function regenerate() {
    setWorking("report");
    setError("");
    setNotice("");
    try {
      const result = await apiFetch<{ dag_run_id: string; state: string }>(
        "/api/admin/reports/regenerate",
        { method: "POST", body: JSON.stringify({ reason: "manual" }) }
      );
      setNotice(`Reporte en generacion: ${result.dag_run_id} (estado ${result.state})`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo regenerar el reporte");
    } finally {
      setWorking("");
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Administracion</h1>
          <p className="muted">
            Acciones privilegiadas y auditoria de las ejecuciones de inteligencia artificial.
          </p>
        </div>
        <button className="btn" onClick={loadRuns}>
          Actualizar
        </button>
      </header>

      {error ? <ErrorBox message={error} /> : null}
      {notice ? <div className="feedback good-message">{notice}</div> : null}

      <section className="grid-two">
        <div className="panel">
          <div className="panel-title">
            <h2>Backfill historico</h2>
            <span className="muted">Airflow DAG backfill_usgs</span>
          </div>
          <p className="muted">
            Carga los ultimos dias desde el endpoint de consulta USGS. El upsert evita duplicados.
          </p>
          <div className="inline-form">
            <label>
              Dias
              <input
                type="number"
                min={1}
                max={60}
                value={days}
                onChange={(event) => setDays(Number(event.target.value))}
              />
            </label>
            <button className="btn primary" onClick={launchBackfill} disabled={!!working}>
              {working === "backfill" ? "Lanzando..." : "Lanzar backfill"}
            </button>
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">
            <h2>Reporte con IA</h2>
            <span className="muted">Airflow DAG daily_ai</span>
          </div>
          <p className="muted">
            Calcula anomalias y regenera el informe del dia. Si el proveedor IA falla, se usa el
            reporte determinista.
          </p>
          <button className="btn primary" onClick={regenerate} disabled={!!working}>
            {working === "report" ? "Lanzando..." : "Regenerar reporte"}
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">
          <h2>Auditoria de IA</h2>
          <span className="muted">Modelo, tokens, latencia y costo</span>
        </div>
        {loading ? <Loading label="Cargando ejecuciones" /> : null}
        {!loading && runs.length === 0 ? (
          <Empty message="Sin ejecuciones de IA registradas." />
        ) : null}
        {!loading && runs.length > 0 ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Tipo</th>
                  <th>Modelo</th>
                  <th>Prompt</th>
                  <th>Tokens</th>
                  <th>Latencia</th>
                  <th>Costo</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr key={run.id}>
                    <td>{formatDate(run.created_at)}</td>
                    <td>{run.kind}</td>
                    <td>{run.model}</td>
                    <td>{run.prompt_version}</td>
                    <td>
                      {run.tokens_in} / {run.tokens_out}
                    </td>
                    <td>{run.latency_ms} ms</td>
                    <td>{formatNumber(run.cost_estimate, 4)}</td>
                    <td>
                      <span className={`tag ${run.success ? "good" : "warn"}`}>
                        {run.success ? "ok" : "fallback"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  );
}
