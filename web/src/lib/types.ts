export type Role = "viewer" | "admin";

export interface Session {
  token: string;
  role: Role;
  email: string;
}

export interface Kpis {
  events_24h: number;
  events_previous_24h: number;
  max_magnitude: number;
  avg_magnitude: number;
  tsunami_events: number;
  significant_events: number;
  total_events: number;
  quality_score: number;
  quality_checked_at: string | null;
  anomalies_24h: number;
  last_update: string | null;
  freshness_seconds: number | null;
}

export interface EventRow {
  id: string;
  mag: number;
  place: string;
  region: string;
  event_time: string;
  updated_time: string | null;
  tsunami: boolean;
  significance: number | null;
  status: string | null;
  mag_type: string | null;
  event_type: string;
  url: string | null;
  longitude: number;
  latitude: number;
  depth_km: number;
  significant: boolean;
  updated_at: string;
}

export interface EventsResponse {
  items: EventRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface TimeseriesPoint {
  bucket: string;
  events: number;
  max_magnitude: number;
  avg_magnitude: number;
}

export interface RegionStat {
  region: string;
  events: number;
  max_magnitude: number;
  avg_magnitude: number;
}

export interface MagnitudeBucket {
  bucket: string;
  events: number;
}

export interface ReportRow {
  id: number;
  report_date: string;
  title: string;
  summary: string;
  highlights: string[];
  statistics: Record<string, unknown>;
  model: string;
  prompt_version: string;
  status: string;
  numbers_valid: boolean;
  generated_at: string;
}

export interface ReportsResponse {
  items: ReportRow[];
  total: number;
  page: number;
  page_size: number;
}

export interface QualityMetric {
  dag_run_id: string;
  checked_at: string;
  total: number;
  passed: number;
  rejected: number;
  score: number;
  gate_passed: boolean;
  rules?: unknown;
  details?: Record<string, unknown>;
}

export interface DagRun {
  dag_id: string;
  run_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  message: string | null;
  details?: Record<string, unknown>;
}

export interface Anomaly {
  id?: number;
  detected_at?: string;
  window_start: string;
  window_end?: string;
  method?: string;
  score: number;
  event_count: number;
  expected: number;
  severity: string;
  explanation: string;
}

export interface PipelineStatus {
  runs: DagRun[];
  quality: QualityMetric | null;
  quality_history?: QualityMetric[];
  run_history?: DagRun[];
  freshness_seconds: number | null;
  last_update: string | null;
  anomalies: Anomaly[];
}

export interface AskResponse {
  question: string;
  answer: string;
  answer_provider: string;
  intent: string | null;
  sql: string | null;
  explanation: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  provider: string;
  validated: boolean;
}

export interface AiRun {
  id: number;
  kind: string;
  model: string;
  prompt_version: string;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  cost_estimate: number;
  success: boolean;
  error: string | null;
  created_at: string;
}
