#!/usr/bin/env bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
CREATE ROLE airflow LOGIN PASSWORD '${AIRFLOW_DB_PASSWORD}';
CREATE DATABASE airflow OWNER airflow;
CREATE DATABASE sismowatch;
CREATE ROLE ingest_writer LOGIN PASSWORD '${INGEST_DB_PASSWORD}';
CREATE ROLE transform_writer LOGIN PASSWORD '${TRANSFORM_DB_PASSWORD}';
CREATE ROLE api_reader LOGIN PASSWORD '${READER_DB_PASSWORD}';
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname sismowatch <<-EOSQL
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA raw;
CREATE SCHEMA staging;
CREATE SCHEMA curated;
CREATE SCHEMA quality;
CREATE SCHEMA pipeline;
CREATE SCHEMA ai;
CREATE SCHEMA app;

CREATE TABLE raw.usgs_responses (
  id bigserial PRIMARY KEY,
  endpoint text NOT NULL,
  fetched_at timestamptz NOT NULL DEFAULT now(),
  http_status integer NOT NULL,
  feature_count integer NOT NULL,
  payload jsonb NOT NULL
);

CREATE TABLE raw.events (
  id text PRIMARY KEY,
  payload jsonb NOT NULL,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  last_response_id bigint REFERENCES raw.usgs_responses(id)
);

CREATE INDEX raw_events_last_seen_idx ON raw.events(last_seen_at DESC);

CREATE TABLE staging.events (
  id text PRIMARY KEY,
  mag double precision,
  place text,
  region text,
  event_time timestamptz NOT NULL,
  updated_time timestamptz,
  tsunami boolean,
  significance integer,
  status text,
  mag_type text,
  event_type text,
  url text,
  longitude double precision,
  latitude double precision,
  depth_km double precision,
  hour_bucket timestamptz NOT NULL,
  staged_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE curated.events (
  id text PRIMARY KEY,
  mag numeric(4,2) NOT NULL,
  place text NOT NULL,
  region text NOT NULL,
  event_time timestamptz NOT NULL,
  updated_time timestamptz,
  tsunami boolean NOT NULL DEFAULT false,
  significance integer,
  status text,
  mag_type text,
  event_type text NOT NULL,
  url text,
  longitude numeric(8,5) NOT NULL,
  latitude numeric(7,5) NOT NULL,
  depth_km numeric(6,2) NOT NULL,
  hour_bucket timestamptz NOT NULL,
  significant boolean NOT NULL DEFAULT false,
  curated_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX curated_events_time_idx ON curated.events(event_time DESC);
CREATE INDEX curated_events_mag_idx ON curated.events(mag DESC);
CREATE INDEX curated_events_region_idx ON curated.events(region);
CREATE INDEX curated_events_hour_idx ON curated.events(hour_bucket);
CREATE INDEX curated_events_updated_idx ON curated.events(updated_at DESC);

CREATE TABLE quality.metrics (
  id bigserial PRIMARY KEY,
  dag_run_id text NOT NULL,
  checked_at timestamptz NOT NULL DEFAULT now(),
  total integer NOT NULL,
  passed integer NOT NULL,
  rejected integer NOT NULL,
  score numeric(5,2) NOT NULL,
  gate_passed boolean NOT NULL,
  rules jsonb NOT NULL,
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE pipeline.runs (
  id bigserial PRIMARY KEY,
  dag_id text NOT NULL,
  run_id text NOT NULL,
  status text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  message text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX pipeline_runs_dag_idx ON pipeline.runs(dag_id, started_at DESC);

CREATE TABLE ai.reports (
  id bigserial PRIMARY KEY,
  report_date date NOT NULL UNIQUE,
  title text NOT NULL,
  summary text NOT NULL,
  highlights jsonb NOT NULL,
  statistics jsonb NOT NULL,
  model text NOT NULL,
  prompt_version text NOT NULL,
  status text NOT NULL,
  numbers_valid boolean NOT NULL,
  generated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai.anomalies (
  id bigserial PRIMARY KEY,
  detected_at timestamptz NOT NULL DEFAULT now(),
  window_start timestamptz NOT NULL,
  window_end timestamptz NOT NULL,
  method text NOT NULL,
  score numeric(8,3) NOT NULL,
  event_count integer NOT NULL,
  expected numeric(8,3) NOT NULL,
  severity text NOT NULL,
  explanation text NOT NULL,
  UNIQUE (window_start, method)
);

CREATE TABLE ai.runs (
  id bigserial PRIMARY KEY,
  kind text NOT NULL,
  model text NOT NULL,
  prompt_version text NOT NULL,
  tokens_in integer NOT NULL DEFAULT 0,
  tokens_out integer NOT NULL DEFAULT 0,
  latency_ms integer NOT NULL DEFAULT 0,
  cost_estimate numeric(10,6) NOT NULL DEFAULT 0,
  success boolean NOT NULL,
  error text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE ai.query_log (
  id bigserial PRIMARY KEY,
  question text NOT NULL,
  sql text,
  provider text NOT NULL,
  success boolean NOT NULL,
  latency_ms integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.users (
  id bigserial PRIMARY KEY,
  email text NOT NULL UNIQUE,
  password_hash text NOT NULL,
  role text NOT NULL CHECK (role IN ('viewer','admin')),
  created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO app.users (email, password_hash, role) VALUES
  ('${ADMIN_EMAIL}', crypt('${ADMIN_PASSWORD}', gen_salt('bf')), 'admin'),
  ('${VIEWER_EMAIL}', crypt('${VIEWER_PASSWORD}', gen_salt('bf')), 'viewer');

GRANT CONNECT ON DATABASE sismowatch TO ingest_writer, transform_writer, api_reader;

GRANT USAGE ON SCHEMA raw TO ingest_writer, transform_writer;
GRANT USAGE ON SCHEMA staging, curated, quality, pipeline, ai TO transform_writer;
GRANT USAGE ON SCHEMA curated, quality, pipeline, ai, app TO api_reader;

GRANT SELECT, INSERT, UPDATE ON raw.events TO ingest_writer;
GRANT SELECT, INSERT ON raw.usgs_responses TO ingest_writer;
GRANT USAGE, SELECT ON SEQUENCE raw.usgs_responses_id_seq TO ingest_writer;

GRANT SELECT ON raw.events, raw.usgs_responses TO transform_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON staging.events TO transform_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON curated.events TO transform_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON quality.metrics TO transform_writer;
GRANT USAGE, SELECT ON SEQUENCE quality.metrics_id_seq TO transform_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON pipeline.runs TO transform_writer;
GRANT USAGE, SELECT ON SEQUENCE pipeline.runs_id_seq TO transform_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ai.reports, ai.anomalies, ai.runs TO transform_writer;
GRANT USAGE, SELECT ON SEQUENCE ai.reports_id_seq, ai.anomalies_id_seq, ai.runs_id_seq TO transform_writer;

GRANT SELECT ON curated.events TO api_reader;
GRANT SELECT ON quality.metrics TO api_reader;
GRANT SELECT ON pipeline.runs TO api_reader;
GRANT SELECT ON ai.reports, ai.anomalies, ai.runs TO api_reader;
GRANT SELECT ON app.users TO api_reader;
GRANT INSERT ON ai.query_log TO api_reader;
GRANT USAGE, SELECT ON SEQUENCE ai.query_log_id_seq TO api_reader;
EOSQL
