import json
import re
import time
from datetime import datetime, timezone

import pandas as pd
import requests
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field, ValidationError

from include.settings import (
    LLM_TIMEOUT_SECONDS,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    PROMPTS_DIR,
)

PROMPT_VERSION = "report_v3"
ANOMALY_METHOD = "zscore_hourly"


class ReportPayload(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    summary: str = Field(min_length=40, max_length=1200)
    highlights: list[str] = Field(min_length=3, max_length=6)


def _as_float(value):
    return float(value) if value is not None else None


def _as_iso(value):
    return value.isoformat() if value is not None else None


def _utc_timestamp(value):
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def collect_stats(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                count(*) AS events_24h,
                COALESCE(max(mag), 0) AS max_magnitude,
                COALESCE(avg(mag), 0) AS avg_magnitude,
                count(*) FILTER (WHERE tsunami) AS tsunami_events,
                count(*) FILTER (WHERE significant) AS significant_events
            FROM curated.events
            WHERE event_time >= now() - interval '24 hours'
            """
        )
        recent = dict(cur.fetchone())
        cur.execute(
            """
            SELECT count(*) AS events_previous_24h
            FROM curated.events
            WHERE event_time >= now() - interval '48 hours'
              AND event_time < now() - interval '24 hours'
            """
        )
        previous = dict(cur.fetchone())
        cur.execute(
            """
            SELECT id, mag, place, region, event_time
            FROM curated.events
            WHERE event_time >= now() - interval '24 hours'
            ORDER BY mag DESC NULLS LAST
            LIMIT 1
            """
        )
        strongest = cur.fetchone()
        cur.execute(
            """
            SELECT region, count(*) AS events
            FROM curated.events
            WHERE event_time >= now() - interval '24 hours'
            GROUP BY region
            ORDER BY events DESC
            LIMIT 5
            """
        )
        regions = [dict(row) for row in cur.fetchall()]
        cur.execute(
            "SELECT score, checked_at FROM quality.metrics ORDER BY checked_at DESC LIMIT 1"
        )
        quality = cur.fetchone()
        cur.execute("SELECT max(updated_at) AS last_update FROM curated.events")
        last_update = cur.fetchone()
        cur.execute(
            """
            SELECT count(*) AS anomalies_24h
            FROM ai.anomalies
            WHERE detected_at >= now() - interval '24 hours'
            """
        )
        anomalies = dict(cur.fetchone())
        cur.execute(
            """
            SELECT window_start, event_count, expected, score, severity, explanation
            FROM ai.anomalies
            WHERE detected_at >= now() - interval '48 hours'
            ORDER BY window_start DESC
            LIMIT 5
            """
        )
        anomaly_rows = [dict(row) for row in cur.fetchall()]

    stats = {
        "window_hours": 24,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events_24h": int(recent["events_24h"]),
        "events_previous_24h": int(previous["events_previous_24h"]),
        "max_magnitude": round(float(recent["max_magnitude"]), 2),
        "avg_magnitude": round(float(recent["avg_magnitude"]), 2),
        "tsunami_events": int(recent["tsunami_events"]),
        "significant_events": int(recent["significant_events"]),
        "top_regions": [
            {"region": row["region"], "events": int(row["events"])} for row in regions
        ],
        "strongest_event": None
        if strongest is None
        else {
            "id": strongest["id"],
            "mag": round(float(strongest["mag"]), 2),
            "place": strongest["place"],
            "region": strongest["region"],
            "event_time": _as_iso(strongest["event_time"]),
        },
        "quality_score": round(float(quality["score"]), 2) if quality else 0.0,
        "quality_checked_at": _as_iso(quality["checked_at"]) if quality else None,
        "last_update": _as_iso(last_update["last_update"]) if last_update else None,
        "anomalies_24h": int(anomalies["anomalies_24h"]),
        "recent_anomalies": [
            {
                "window_start": _as_iso(row["window_start"]),
                "event_count": int(row["event_count"]),
                "expected": round(float(row["expected"]), 2),
                "score": round(float(row["score"]), 2),
                "severity": row["severity"],
                "explanation": row["explanation"],
            }
            for row in anomaly_rows
        ],
    }
    return stats


def detect_anomalies(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT hour_bucket, count(*) AS events
            FROM curated.events
            WHERE event_time >= now() - interval '7 days'
            GROUP BY hour_bucket
            ORDER BY hour_bucket
            """
        )
        rows = cur.fetchall()
    if not rows:
        return 0
    counts = pd.Series(
        {_utc_timestamp(row["hour_bucket"]): int(row["events"]) for row in rows}
    )
    end = pd.Timestamp.now(tz="UTC").floor("h")
    index = pd.date_range(end=end, periods=168, freq="h", tz="UTC")
    series = counts.reindex(index, fill_value=0).astype(float)
    mean = float(series.mean())
    std = float(series.std(ddof=0))
    if std == 0:
        return 0
    detected = []
    for hour, value in series.items():
        score = (value - mean) / std
        if value >= 5 and score >= 3:
            severity = "alta" if score >= 5 else "media" if score >= 4 else "baja"
            explanation = (
                f"Se registraron {int(value)} eventos sismicos entre "
                f"{hour.isoformat()} y {(hour + pd.Timedelta(hours=1)).isoformat()}, "
                f"frente a un promedio horario de {mean:.2f} eventos "
                f"(z-score {score:.2f}, severidad {severity})."
            )
            detected.append(
                (
                    hour.to_pydatetime(),
                    (hour + pd.Timedelta(hours=1)).to_pydatetime(),
                    round(score, 3),
                    int(value),
                    round(mean, 3),
                    severity,
                    explanation,
                )
            )
    if not detected:
        return 0
    with conn.cursor() as cur:
        for window_start, window_end, score, value, expected, severity, explanation in detected:
            cur.execute(
                """
                INSERT INTO ai.anomalies (
                    window_start, window_end, method, score, event_count,
                    expected, severity, explanation
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (window_start, method) DO UPDATE SET
                    window_end = EXCLUDED.window_end,
                    score = EXCLUDED.score,
                    event_count = EXCLUDED.event_count,
                    expected = EXCLUDED.expected,
                    severity = EXCLUDED.severity,
                    explanation = EXCLUDED.explanation
                """,
                (
                    window_start,
                    window_end,
                    ANOMALY_METHOD,
                    score,
                    value,
                    expected,
                    severity,
                    explanation,
                ),
            )
    return len(detected)


def _prompt_text():
    return (PROMPTS_DIR / f"{PROMPT_VERSION}.txt").read_text(encoding="utf-8")


def ollama_generate(prompt):
    started = time.perf_counter()
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": 600},
        },
        timeout=LLM_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    return {
        "text": payload.get("response", ""),
        "model": payload.get("model", OLLAMA_MODEL),
        "tokens_in": int(payload.get("prompt_eval_count", 0)),
        "tokens_out": int(payload.get("eval_count", 0)),
        "latency_ms": int((time.perf_counter() - started) * 1000),
    }


def _numbers_from(value, acc):
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        acc.add(round(float(value), 2))
    elif isinstance(value, dict):
        for item in value.values():
            _numbers_from(item, acc)
    elif isinstance(value, list):
        for item in value:
            _numbers_from(item, acc)


def allowed_numbers(stats):
    allowed = set()
    _numbers_from(stats, allowed)
    now = datetime.now(timezone.utc)
    allowed.update({0, 1, now.year, now.month, now.day, (now - pd.Timedelta(days=1)).day})
    events = stats.get("events_24h", 0)
    if events:
        for key in ("tsunami_events", "significant_events", "events_previous_24h"):
            allowed.add(round(stats.get(key, 0) / events * 100, 1))
        allowed.add(round(stats.get("significant_events", 0) / events * 100, 0))
    for value in list(allowed):
        allowed.add(round(value, 0))
        allowed.add(round(value, 1))
    return allowed


def numbers_match(text, stats):
    allowed = allowed_numbers(stats)
    tokens = re.findall(r"\d+(?:[.,]\d+)?", text)
    for token in tokens:
        number = float(token.replace(",", "."))
        if not any(abs(number - candidate) <= max(0.01, abs(candidate) * 0.01) for candidate in allowed):
            return False
    return True


def statements_match(text, stats):
    normalized = re.sub(r"\s+", " ", text.lower())
    normalized = re.sub(r"[áàä]", "a", normalized)
    normalized = re.sub(r"[éèë]", "e", normalized)
    normalized = re.sub(r"[íìï]", "i", normalized)
    normalized = re.sub(r"[óòö]", "o", normalized)
    normalized = re.sub(r"[úùü]", "u", normalized)
    absence_patterns = (
        r"sin (eventos |sismos )?significativ",
        r"no hubo (eventos |sismos )?significativ",
        r"ningun (evento |sismo )?significativ",
        r"sin (eventos |alertas )?de tsunami",
        r"no hubo (eventos |alertas )?de tsunami",
    )
    if stats.get("significant_events", 0) and any(
        re.search(pattern, normalized) for pattern in absence_patterns[:3]
    ):
        return False
    if stats.get("tsunami_events", 0) and any(
        re.search(pattern, normalized) for pattern in absence_patterns[3:]
    ):
        return False
    if stats.get("anomalies_24h", 0) and re.search(r"sin anomal|no hubo anomal|ninguna anomal", normalized):
        return False
    events = stats.get("events_24h", 0)
    previous = stats.get("events_previous_24h", 0)
    if events < previous and re.search(
        r"super(ando|o)|aument(o|aron)|increment(o|aron)|mas (eventos|sismos) que",
        normalized,
    ):
        return False
    if events > previous and re.search(
        r"descend(io|ieron)|disminuy(o|eron)|reduj(o|eron)|menos (eventos|sismos) que",
        normalized,
    ):
        return False
    return True


def fallback_report(stats):
    date_label = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    region = stats["top_regions"][0] if stats["top_regions"] else None
    summary = (
        f"En las ultimas 24 horas se registraron {stats['events_24h']} eventos sismicos, "
        f"con una magnitud maxima de {stats['max_magnitude']} y un promedio de "
        f"{stats['avg_magnitude']}. Se detectaron {stats['tsunami_events']} eventos con "
        f"alerta de tsunami y {stats['significant_events']} eventos significativos. "
        f"El puntaje de calidad mas reciente es {stats['quality_score']}."
    )
    highlights = [
        f"Actividad total: {stats['events_24h']} eventos en 24 horas.",
        f"Magnitud maxima: {stats['max_magnitude']}.",
        f"Eventos con alerta de tsunami: {stats['tsunami_events']}.",
    ]
    if region:
        highlights.append(
            f"Region mas activa: {region['region']} con {region['events']} eventos."
        )
    else:
        highlights.append("Sin regiones con actividad registrada en la ventana.")
    if stats["strongest_event"]:
        highlights.append(
            f"Evento mas fuerte: magnitud {stats['strongest_event']['mag']} en "
            f"{stats['strongest_event']['place']}."
        )
    return ReportPayload(
        title=f"Reporte sismico {date_label}",
        summary=summary,
        highlights=highlights[:5],
    )


def _parse_payload(text):
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("La respuesta del modelo no contiene JSON")
    data = json.loads(text[start : end + 1])
    return ReportPayload.model_validate(data)


def save_report(conn, report, stats, model, status, numbers_valid):
    report_date = datetime.now(timezone.utc).date()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ai.reports (
                report_date, title, summary, highlights, statistics, model,
                prompt_version, status, numbers_valid
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (report_date) DO UPDATE SET
                title = EXCLUDED.title,
                summary = EXCLUDED.summary,
                highlights = EXCLUDED.highlights,
                statistics = EXCLUDED.statistics,
                model = EXCLUDED.model,
                prompt_version = EXCLUDED.prompt_version,
                status = EXCLUDED.status,
                numbers_valid = EXCLUDED.numbers_valid,
                generated_at = now()
            """,
            (
                report_date,
                report.title,
                report.summary,
                json.dumps(report.highlights),
                json.dumps(stats),
                model,
                PROMPT_VERSION,
                status,
                numbers_valid,
            ),
        )


def log_ai_run(conn, kind, model, tokens_in, tokens_out, latency_ms, success, error=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ai.runs (
                kind, model, prompt_version, tokens_in, tokens_out,
                latency_ms, cost_estimate, success, error
            ) VALUES (%s, %s, %s, %s, %s, %s, 0, %s, %s)
            """,
            (
                kind,
                model,
                PROMPT_VERSION,
                tokens_in,
                tokens_out,
                latency_ms,
                success,
                (error or "")[:500] if error else None,
            ),
        )


def generate_report(conn):
    stats = collect_stats(conn)
    prompt = _prompt_text().replace("{{DATA}}", json.dumps(stats, ensure_ascii=False))
    fallback = fallback_report(stats)
    try:
        result = ollama_generate(prompt)
        parsed = _parse_payload(result["text"])
        full_text = parsed.summary + " " + " ".join(parsed.highlights)
        valid = numbers_match(full_text, stats) and statements_match(full_text, stats)
        if not valid:
            parsed = fallback
            status = "fallback_validacion"
            valid = True
        else:
            status = "ollama"
        save_report(conn, parsed, stats, result["model"], status, valid)
        log_ai_run(
            conn,
            "report",
            result["model"],
            result["tokens_in"],
            result["tokens_out"],
            result["latency_ms"],
            True,
        )
        return {"status": status, "model": result["model"], "numbers_valid": valid}
    except (requests.RequestException, ValueError, ValidationError, KeyError) as exc:
        save_report(conn, fallback, stats, "reglas", "fallback_ia", True)
        log_ai_run(conn, "report", "reglas", 0, 0, 0, False, str(exc))
        return {"status": "fallback_ia", "model": "reglas", "numbers_valid": True}
