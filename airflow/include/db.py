from contextlib import contextmanager

import psycopg2
from psycopg2.extras import Json, RealDictCursor, execute_values

from include.settings import INGEST_DSN, TRANSFORM_DSN


@contextmanager
def connection(dsn):
    conn = psycopg2.connect(dsn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def persist_feed(payload, endpoint):
    features = payload.get("features") or []
    unique = {}
    for feature in features:
        event_id = feature.get("id")
        if event_id:
            unique[event_id] = feature
    rows = [(event_id, Json(feature)) for event_id, feature in unique.items()]
    with connection(INGEST_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw.usgs_responses (endpoint, http_status, feature_count, payload)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (endpoint, 200, len(features), Json(payload)),
            )
            response_id = cur.fetchone()[0]
            if rows:
                execute_values(
                    cur,
                    """
                    INSERT INTO raw.events (id, payload, first_seen_at, last_seen_at, last_response_id)
                    VALUES %s
                    ON CONFLICT (id) DO UPDATE SET
                        payload = EXCLUDED.payload,
                        last_seen_at = now(),
                        last_response_id = EXCLUDED.last_response_id
                    """,
                    [
                        (event_id, feature, response_id)
                        for event_id, feature in rows
                    ],
                    template="(%s, %s, now(), now(), %s)",
                    page_size=500,
                )
    return {
        "features": len(features),
        "unique_events": len(rows),
        "response_id": response_id,
    }


def read_raw_events():
    with connection(TRANSFORM_DSN) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, payload FROM raw.events ORDER BY last_seen_at")
            return [dict(row) for row in cur.fetchall()]


def upsert_staging(rows):
    if not rows:
        return 0
    values = [
        (
            row["id"],
            row["mag"],
            row["place"],
            row["region"],
            row["event_time"],
            row["updated_time"],
            row["tsunami"],
            row["significance"],
            row["status"],
            row["mag_type"],
            row["event_type"],
            row["url"],
            row["longitude"],
            row["latitude"],
            row["depth_km"],
            row["hour_bucket"],
        )
        for row in rows
    ]
    with connection(TRANSFORM_DSN) as conn:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO staging.events (
                    id, mag, place, region, event_time, updated_time, tsunami,
                    significance, status, mag_type, event_type, url, longitude,
                    latitude, depth_km, hour_bucket
                ) VALUES %s
                ON CONFLICT (id) DO UPDATE SET
                    mag = EXCLUDED.mag,
                    place = EXCLUDED.place,
                    region = EXCLUDED.region,
                    event_time = EXCLUDED.event_time,
                    updated_time = EXCLUDED.updated_time,
                    tsunami = EXCLUDED.tsunami,
                    significance = EXCLUDED.significance,
                    status = EXCLUDED.status,
                    mag_type = EXCLUDED.mag_type,
                    event_type = EXCLUDED.event_type,
                    url = EXCLUDED.url,
                    longitude = EXCLUDED.longitude,
                    latitude = EXCLUDED.latitude,
                    depth_km = EXCLUDED.depth_km,
                    hour_bucket = EXCLUDED.hour_bucket,
                    staged_at = now()
                """,
                values,
                page_size=500,
            )
    return len(values)


def insert_quality_metrics(run_id, total, passed, rejected, score, gate_passed, rules, details):
    with connection(TRANSFORM_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO quality.metrics (
                    dag_run_id, total, passed, rejected, score, gate_passed, rules, details
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    total,
                    passed,
                    rejected,
                    score,
                    gate_passed,
                    Json(rules),
                    Json(details),
                ),
            )


def publish_curated():
    with connection(TRANSFORM_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO curated.events (
                    id, mag, place, region, event_time, updated_time, tsunami,
                    significance, status, mag_type, event_type, url, longitude,
                    latitude, depth_km, hour_bucket, significant
                )
                SELECT
                    id, mag, place, region, event_time, updated_time, tsunami,
                    significance, status, mag_type, event_type, url, longitude,
                    latitude, depth_km, hour_bucket,
                    (mag >= 4.5 OR tsunami = true OR significance >= 600)
                FROM staging.events
                ON CONFLICT (id) DO UPDATE SET
                    mag = EXCLUDED.mag,
                    place = EXCLUDED.place,
                    region = EXCLUDED.region,
                    event_time = EXCLUDED.event_time,
                    updated_time = EXCLUDED.updated_time,
                    tsunami = EXCLUDED.tsunami,
                    significance = EXCLUDED.significance,
                    status = EXCLUDED.status,
                    mag_type = EXCLUDED.mag_type,
                    event_type = EXCLUDED.event_type,
                    url = EXCLUDED.url,
                    longitude = EXCLUDED.longitude,
                    latitude = EXCLUDED.latitude,
                    depth_km = EXCLUDED.depth_km,
                    hour_bucket = EXCLUDED.hour_bucket,
                    significant = EXCLUDED.significant,
                    updated_at = now()
                WHERE curated.events.mag IS DISTINCT FROM EXCLUDED.mag
                   OR curated.events.place IS DISTINCT FROM EXCLUDED.place
                   OR curated.events.region IS DISTINCT FROM EXCLUDED.region
                   OR curated.events.event_time IS DISTINCT FROM EXCLUDED.event_time
                   OR curated.events.updated_time IS DISTINCT FROM EXCLUDED.updated_time
                   OR curated.events.tsunami IS DISTINCT FROM EXCLUDED.tsunami
                   OR curated.events.significance IS DISTINCT FROM EXCLUDED.significance
                   OR curated.events.status IS DISTINCT FROM EXCLUDED.status
                   OR curated.events.mag_type IS DISTINCT FROM EXCLUDED.mag_type
                   OR curated.events.event_type IS DISTINCT FROM EXCLUDED.event_type
                   OR curated.events.url IS DISTINCT FROM EXCLUDED.url
                   OR curated.events.longitude IS DISTINCT FROM EXCLUDED.longitude
                   OR curated.events.latitude IS DISTINCT FROM EXCLUDED.latitude
                   OR curated.events.depth_km IS DISTINCT FROM EXCLUDED.depth_km
                   OR curated.events.hour_bucket IS DISTINCT FROM EXCLUDED.hour_bucket
                   OR curated.events.significant IS DISTINCT FROM EXCLUDED.significant
                """
            )
            return cur.rowcount


def curated_count():
    with connection(TRANSFORM_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM curated.events")
            return cur.fetchone()[0]


def record_pipeline_run(dag_id, run_id, status, message=None, details=None):
    started_at = (details or {}).get("started_at")
    finished_at = (details or {}).get("finished_at")
    with connection(TRANSFORM_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline.runs (
                    dag_id, run_id, status, started_at, finished_at, message, details
                ) VALUES (%s, %s, %s, COALESCE(%s, now()), %s, %s, %s)
                """,
                (
                    dag_id,
                    run_id,
                    status,
                    started_at,
                    finished_at,
                    (message or "")[:500],
                    Json(details or {}),
                ),
            )
