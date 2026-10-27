import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { apiFetch } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDate, formatFreshness, formatNumber } from "../lib/format";
import type {
  EventRow,
  EventsResponse,
  Kpis,
  MagnitudeBucket,
  PipelineStatus,
  RegionStat,
  TimeseriesPoint
} from "../lib/types";
import { Empty, ErrorBox, LiveBadge, Loading } from "../components/Feedback";
import { KpiCard } from "../components/KpiCard";

const COLORS = ["#22c55e", "#38bdf8", "#eab308", "#f97316", "#ef4444"];

function magnitudeColor(mag: number): string {
  if (mag >= 6) return "#ef4444";
  if (mag >= 5) return "#f97316";
  if (mag >= 4) return "#eab308";
  if (mag >= 3) return "#38bdf8";
  return "#22c55e";
}

function hourLabel(value: string): string {
  const date = new Date(value);
  return `${date.getHours().toString().padStart(2, "0")}:00`;
}

export function Dashboard() {
  const { session } = useAuth();
  const [kpis, setKpis] = useState<Kpis | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [regions, setRegions] = useState<RegionStat[]>([]);
  const [magnitude, setMagnitude] = useState<MagnitudeBucket[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [hours, setHours] = useState(24);
  const [minMagnitude, setMinMagnitude] = useState("");
  const [region, setRegion] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [liveEvents, setLiveEvents] = useState<EventRow[]>([]);
  const [connected, setConnected] = useState(false);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const eventParams = new URLSearchParams({
        limit: "100",
        sort: "event_time",
        order: "desc",
        start: new Date(Date.now() - hours * 3600 * 1000).toISOString()
      });
      if (minMagnitude) eventParams.set("min_magnitude", minMagnitude);
      if (region) eventParams.set("region", region);
      const [kpiData, seriesData, regionData, magnitudeData, eventData, pipelineData] =
        await Promise.all([
          apiFetch<Kpis>("/api/kpis"),
          apiFetch<TimeseriesPoint[]>(`/api/stats/timeseries?hours=${hours}`),
          apiFetch<RegionStat[]>("/api/stats/regions?days=30&limit=30"),
          apiFetch<MagnitudeBucket[]>("/api/stats/magnitude"),
          apiFetch<EventsResponse>(`/api/events?${eventParams.toString()}`),
          apiFetch<PipelineStatus>("/api/pipeline/status")
        ]);
      setKpis(kpiData);
      setTimeseries(seriesData);
      setRegions(regionData);
      setMagnitude(magnitudeData);
      setEvents(eventData.items);
      setPipeline(pipelineData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar los datos");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [hours, minMagnitude, region]);

  useEffect(() => {
    if (!session) return;
    const source = new EventSource(
      `/api/stream?token=${encodeURIComponent(session.token)}`
    );
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as EventRow;
        setLiveEvents((current) => {
          const next = [event, ...current.filter((item) => item.id !== event.id)];
          return next.slice(0, 25);
        });
      } catch {
        setConnected(false);
      }
    };
    return () => source.close();
  }, [session]);

  const mapEvents = useMemo(() => {
    const merged = [...liveEvents, ...events];
    const unique = new Map<string, EventRow>();
    merged.forEach((event) => unique.set(event.id, event));
    return Array.from(unique.values()).slice(0, 250);
  }, [liveEvents, events]);

  const topRegions = useMemo(
    () => regions.slice(0, 8).map((item) => ({ ...item, name: item.region })),
    [regions]
  );

  const qualityTone =
    (kpis?.quality_score || 0) >= 95
      ? "good"
      : (kpis?.quality_score || 0) >= 80
        ? "warn"
        : "danger";

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Panel sismico global</h1>
          <p className="muted">
            Feed USGS procesado por raw, staging y curated. Ultima actualizacion:{" "}
            {formatDate(kpis?.last_update)}
          </p>
        </div>
        <div className="header-actions">
          <LiveBadge connected={connected} />
          <button className="btn" onClick={load} disabled={loading}>
            Actualizar
          </button>
        </div>
      </header>

      {error ? <ErrorBox message={error} onRetry={load} /> : null}
      {loading && !kpis ? <Loading /> : null}

      {kpis ? (
        <>
          <section className="kpi-grid">
            <KpiCard
              label="Eventos 24 h"
              value={kpis.events_24h.toLocaleString("es-CO")}
              hint={`${kpis.events_previous_24h} en las 24 h previas`}
            />
            <KpiCard
              label="Magnitud maxima"
              value={formatNumber(kpis.max_magnitude, 2)}
              tone={kpis.max_magnitude >= 6 ? "danger" : "good"}
              hint="Ventana de 24 h"
            />
            <KpiCard
              label="Magnitud promedio"
              value={formatNumber(kpis.avg_magnitude, 2)}
              hint="Ventana de 24 h"
            />
            <KpiCard
              label="Alertas de tsunami"
              value={kpis.tsunami_events}
              tone={kpis.tsunami_events > 0 ? "danger" : "good"}
              hint={`${kpis.significant_events} eventos significativos`}
            />
            <KpiCard
              label="Calidad de datos"
              value={`${formatNumber(kpis.quality_score, 1)}%`}
              tone={qualityTone}
              hint={`Gate: ${pipeline?.quality?.gate_passed ? "aprobado" : "sin evaluar"}`}
            />
            <KpiCard
              label="Frescura"
              value={formatFreshness(kpis.freshness_seconds)}
              tone={(kpis.freshness_seconds || 0) > 900 ? "warn" : "good"}
              hint={`${kpis.total_events.toLocaleString("es-CO")} eventos en curated`}
            />
            <KpiCard
              label="Anomalias 24 h"
              value={kpis.anomalies_24h}
              tone={kpis.anomalies_24h > 0 ? "warn" : "good"}
              hint="Deteccion z-score por hora"
            />
            <KpiCard
              label="Alcance total"
              value={kpis.total_events.toLocaleString("es-CO")}
              hint="Eventos publicados en curated"
            />
          </section>

          <section className="filters panel">
            <label>
              Ventana
              <select value={hours} onChange={(event) => setHours(Number(event.target.value))}>
                <option value={24}>Ultimas 24 h</option>
                <option value={72}>Ultimos 3 dias</option>
                <option value={168}>Ultimos 7 dias</option>
              </select>
            </label>
            <label>
              Magnitud minima
              <select value={minMagnitude} onChange={(event) => setMinMagnitude(event.target.value)}>
                <option value="">Todas</option>
                <option value="1">1.0</option>
                <option value="2.5">2.5</option>
                <option value="4">4.0</option>
                <option value="5">5.0</option>
              </select>
            </label>
            <label>
              Region
              <select value={region} onChange={(event) => setRegion(event.target.value)}>
                <option value="">Todas</option>
                {regions.map((item) => (
                  <option key={item.region} value={item.region}>
                    {item.region}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="btn ghost"
              onClick={() => {
                setHours(24);
                setMinMagnitude("");
                setRegion("");
              }}
            >
              Limpiar
            </button>
          </section>

          <section className="grid-two">
            <div className="panel">
              <div className="panel-title">
                <h2>Serie temporal</h2>
                <span className="muted">{hours} h</span>
              </div>
              {timeseries.length ? (
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={timeseries}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2b3445" />
                    <XAxis dataKey="bucket" tickFormatter={hourLabel} stroke="#8fa1b8" />
                    <YAxis stroke="#8fa1b8" allowDecimals={false} />
                    <Tooltip
                      contentStyle={{ background: "#111827", border: "1px solid #2b3445" }}
                      labelFormatter={(value) => formatDate(String(value))}
                    />
                    <Line
                      type="monotone"
                      dataKey="events"
                      name="Eventos"
                      stroke="#38bdf8"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <Empty message="Sin datos para la ventana seleccionada." />
              )}
            </div>
            <div className="panel">
              <div className="panel-title">
                <h2>Distribucion por magnitud</h2>
                <span className="muted">30 dias</span>
              </div>
              {magnitude.length ? (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={magnitude}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2b3445" />
                    <XAxis dataKey="bucket" stroke="#8fa1b8" />
                    <YAxis stroke="#8fa1b8" allowDecimals={false} />
                    <Tooltip
                      contentStyle={{ background: "#111827", border: "1px solid #2b3445" }}
                    />
                    <Bar dataKey="events" name="Eventos" radius={[4, 4, 0, 0]}>
                      {magnitude.map((_, index) => (
                        <Cell key={index} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Empty message="Sin distribucion disponible." />
              )}
            </div>
          </section>

          <section className="grid-two">
            <div className="panel map-panel">
              <div className="panel-title">
                <h2>Mapa de eventos</h2>
                <span className="muted">{mapEvents.length} eventos visibles</span>
              </div>
              <div className="map-wrap">
                <MapContainer center={[15, 0]} zoom={2} scrollWheelZoom style={{ height: "100%" }}>
                  <TileLayer
                    attribution="&copy; OpenStreetMap"
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  {mapEvents.map((event) => (
                    <CircleMarker
                      key={event.id}
                      center={[event.latitude, event.longitude]}
                      radius={Math.max(4, Number(event.mag) * 2)}
                      pathOptions={{
                        color: magnitudeColor(Number(event.mag)),
                        fillColor: magnitudeColor(Number(event.mag)),
                        fillOpacity: 0.65,
                        weight: 1
                      }}
                    >
                      <Popup>
                        <strong>M {event.mag}</strong>
                        <br />
                        {event.place}
                        <br />
                        {formatDate(event.event_time)}
                        <br />
                        Profundidad: {event.depth_km} km
                      </Popup>
                    </CircleMarker>
                  ))}
                </MapContainer>
              </div>
            </div>
            <div className="panel">
              <div className="panel-title">
                <h2>Regiones con mas actividad</h2>
                <span className="muted">30 dias</span>
              </div>
              {topRegions.length ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={topRegions} layout="vertical" margin={{ left: 10, right: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2b3445" />
                    <XAxis type="number" stroke="#8fa1b8" allowDecimals={false} />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={120}
                      stroke="#8fa1b8"
                      tick={{ fontSize: 11 }}
                    />
                    <Tooltip
                      contentStyle={{ background: "#111827", border: "1px solid #2b3445" }}
                    />
                    <Bar dataKey="events" name="Eventos" fill="#38bdf8" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <Empty message="Sin regiones registradas." />
              )}
            </div>
          </section>

          <section className="grid-two">
            <div className="panel">
              <div className="panel-title">
                <h2>Eventos en vivo</h2>
                <LiveBadge connected={connected} />
              </div>
              {liveEvents.length === 0 ? (
                <Empty message="Esperando nuevos eventos del feed en tiempo real." />
              ) : (
                <ul className="live-list">
                  {liveEvents.map((event) => (
                    <li key={event.id}>
                      <span className="mag-pill" style={{ background: magnitudeColor(Number(event.mag)) }}>
                        {event.mag}
                      </span>
                      <div>
                        <strong>{event.place}</strong>
                        <small>
                          {formatDate(event.event_time)} · {event.depth_km} km
                        </small>
                      </div>
                      {event.tsunami ? <span className="tag danger">tsunami</span> : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="panel">
              <div className="panel-title">
                <h2>Ultimos eventos filtrados</h2>
                <span className="muted">{events.length} filas</span>
              </div>
              {events.length === 0 ? (
                <Empty message="No hay eventos con los filtros actuales." />
              ) : (
                <div className="table-wrap short">
                  <table>
                    <thead>
                      <tr>
                        <th>Hora</th>
                        <th>Mag</th>
                        <th>Region</th>
                        <th>Lugar</th>
                      </tr>
                    </thead>
                    <tbody>
                      {events.map((event) => (
                        <tr key={event.id}>
                          <td>{formatDate(event.event_time)}</td>
                          <td>
                            <span
                              className="mag-pill small"
                              style={{ background: magnitudeColor(Number(event.mag)) }}
                            >
                              {event.mag}
                            </span>
                          </td>
                          <td>{event.region}</td>
                          <td className="truncate" title={event.place}>
                            {event.place}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
