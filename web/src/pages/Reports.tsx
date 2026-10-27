import { useEffect, useState } from "react";
import { apiFetch, downloadFile, ApiError } from "../lib/api";
import { formatDate } from "../lib/format";
import type { ReportRow, ReportsResponse } from "../lib/types";
import { Empty, ErrorBox, Loading } from "../components/Feedback";

export function Reports() {
  const [data, setData] = useState<ReportsResponse | null>(null);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("report_date");
  const [order, setOrder] = useState("desc");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<ReportRow | null>(null);
  const [exporting, setExporting] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: "8",
        sort,
        order
      });
      if (search) params.set("q", search);
      setData(await apiFetch<ReportsResponse>(`/api/reports?${params.toString()}`));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar los reportes");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, search, sort, order]);

  async function exportAs(format: "csv" | "pdf") {
    setExporting(format);
    setError("");
    try {
      await downloadFile(
        `/api/reports/export?format=${format}`,
        `reportes_sismowatch.${format}`
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo exportar");
    } finally {
      setExporting("");
    }
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Reportes generados con IA</h1>
          <p className="muted">
            Historial de informes diarios. Las cifras se calculan en SQL y se validan contra el
            texto del modelo.
          </p>
        </div>
        <div className="header-actions">
          <button className="btn" onClick={() => exportAs("csv")} disabled={!!exporting}>
            {exporting === "csv" ? "Exportando..." : "Exportar CSV"}
          </button>
          <button className="btn" onClick={() => exportAs("pdf")} disabled={!!exporting}>
            {exporting === "pdf" ? "Exportando..." : "Exportar PDF"}
          </button>
        </div>
      </header>

      {error ? <ErrorBox message={error} onRetry={load} /> : null}

      <section className="panel">
        <div className="toolbar">
          <form
            className="search-form"
            onSubmit={(event) => {
              event.preventDefault();
              setPage(1);
              setSearch(query.trim());
            }}
          >
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Buscar en titulo o resumen"
              maxLength={120}
            />
            <button className="btn" type="submit">
              Buscar
            </button>
          </form>
          <label className="inline-field">
            Orden
            <select
              value={`${sort}:${order}`}
              onChange={(event) => {
                const [nextSort, nextOrder] = event.target.value.split(":");
                setSort(nextSort);
                setOrder(nextOrder);
                setPage(1);
              }}
            >
              <option value="report_date:desc">Fecha descendente</option>
              <option value="report_date:asc">Fecha ascendente</option>
              <option value="generated_at:desc">Generacion reciente</option>
            </select>
          </label>
        </div>

        {loading ? <Loading label="Cargando reportes" /> : null}
        {!loading && data && data.items.length === 0 ? (
          <Empty message="Todavia no hay reportes. Un administrador puede regenerarlos desde Administracion." />
        ) : null}
        {!loading && data && data.items.length > 0 ? (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Titulo</th>
                    <th>Estado</th>
                    <th>Cifras</th>
                    <th>Modelo</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((report) => (
                    <tr key={report.id}>
                      <td>{report.report_date}</td>
                      <td className="truncate" title={report.title}>
                        {report.title}
                      </td>
                      <td>
                        <span className={`tag ${report.status.startsWith("fallback") ? "warn" : "good"}`}>
                          {report.status}
                        </span>
                      </td>
                      <td>
                        <span className={`tag ${report.numbers_valid ? "good" : "danger"}`}>
                          {report.numbers_valid ? "validadas" : "revisar"}
                        </span>
                      </td>
                      <td>{report.model}</td>
                      <td>
                        <button className="btn small" onClick={() => setSelected(report)}>
                          Ver
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="pagination">
              <button className="btn small" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                Anterior
              </button>
              <span>
                Pagina {page} de {totalPages} · {data.total} reportes
              </span>
              <button
                className="btn small"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
              >
                Siguiente
              </button>
            </div>
          </>
        ) : null}
      </section>

      {selected ? (
        <div className="modal-backdrop" onClick={() => setSelected(null)}>
          <div className="modal panel" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>{selected.title}</h2>
                <p className="muted">
                  {selected.report_date} · {formatDate(selected.generated_at)} · {selected.model}
                </p>
              </div>
              <button className="btn small" onClick={() => setSelected(null)}>
                Cerrar
              </button>
            </div>
            <div className="badges">
              <span className={`tag ${selected.numbers_valid ? "good" : "danger"}`}>
                {selected.numbers_valid ? "cifras validadas" : "cifras no validadas"}
              </span>
              <span className="badge">prompt: {selected.prompt_version}</span>
              <span className="badge">estado: {selected.status}</span>
            </div>
            <p className="report-summary">{selected.summary}</p>
            <h3>Puntos destacados</h3>
            <ul className="highlights">
              {selected.highlights.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
            <details className="sql-box">
              <summary>Estadisticas calculadas por el codigo</summary>
              <pre>{JSON.stringify(selected.statistics, null, 2)}</pre>
            </details>
          </div>
        </div>
      ) : null}
    </div>
  );
}
