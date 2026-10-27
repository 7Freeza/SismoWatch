import json
import re
import time
from pathlib import Path

import requests
from fastapi import HTTPException
from sqlalchemy import text
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from app.config import settings
from app.db import ReaderSession, reader_engine
from app.intents import detect_intent
from app.natural_answer import generate_answer
from app.serializers import row_to_dict
from app.text_utils import normalize_text, sanitize_text

PROMPT_VERSION = "nl_sql_v2"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.txt"
MAX_ROWS = 200
BANNED_TOKENS = (
    "--",
    "/*",
    "*/",
    "insert ",
    "update ",
    "delete ",
    "drop ",
    "alter ",
    "create ",
    "truncate ",
    "grant ",
    "copy ",
    "pg_",
    "information_schema",
    "raw.",
    "staging.",
    "quality.",
    "ai.",
    "app.",
)
UNKNOWN_ANSWER = (
    "No pude interpretar la pregunta. Intenta con una consulta sobre magnitud, regiones, "
    "tsunami, profundidad o eventos recientes."
)


def sanitize_question(question):
    return sanitize_text(question, 500)


def format_history(history):
    if not history:
        return "(sin historial)"
    lines = []
    for item in history[-6:]:
        if isinstance(item, dict):
            role = item.get("role", "user")
            content = item.get("content", "")
        else:
            role = getattr(item, "role", "user")
            content = getattr(item, "content", "")
        clean = sanitize_text(str(content), 500)
        if clean:
            speaker = "Usuario" if role == "user" else "Asistente"
            lines.append(f"{speaker}: {clean}")
    return "\n".join(lines) or "(sin historial)"


def extract_window_hours(value):
    normalized = normalize_text(value)
    match = re.search(r"(\d+)\s*horas?", normalized)
    if match:
        return min(max(int(match.group(1)), 1), 720)
    match = re.search(r"(\d+)\s*dias?", normalized)
    if match:
        return min(max(int(match.group(1)) * 24, 1), 1440)
    if "ultima hora" in normalized:
        return 1
    if "hoy" in normalized:
        return 24
    if "semana" in normalized:
        return 168
    if "mes" in normalized:
        return 720
    return 24


def extract_requested_limit(value):
    normalized = normalize_text(value)
    match = re.search(r"(?:ultimos|ultimas|top|primeros|primeras)\s+(\d+)", normalized)
    if match:
        tail = normalized[match.end() :].strip()
        if re.match(r"(horas?|dias?|semanas?|meses?|minutos?)\b", tail):
            return 10
        return min(max(int(match.group(1)), 1), 50)
    match = re.search(r"(\d+)\s+(?:sismos|terremotos|eventos|registros)", normalized)
    if match:
        return min(max(int(match.group(1)), 1), 50)
    return 10


def fallback_sql(question, history_text=""):
    normalized = normalize_text(question)
    combined = normalize_text(f"{question} {history_text}")
    window = extract_window_hours(f"{question} {history_text}")

    if "tsunami" in normalized:
        return (
            "SELECT count(*) AS eventos_con_tsunami FROM curated.events "
            f"WHERE tsunami = true AND event_time >= now() - interval '{window} hours'"
        )
    if ("region" in normalized or "zona" in normalized) and any(
        term in combined for term in ("mas activa", "mas activas", "mayor actividad", "mas actividad", "mas sismos", "mas eventos")
    ):
        return (
            "SELECT region, count(*) AS eventos FROM curated.events "
            "WHERE event_time >= now() - interval '7 days' "
            "GROUP BY region ORDER BY eventos DESC LIMIT 5"
        )
    if "magnitud" in normalized and any(
        term in normalized for term in ("maxima", "mayor", "mas alta", "mas fuerte")
    ):
        return (
            "SELECT id, mag, place, event_time FROM curated.events "
            f"WHERE event_time >= now() - interval '{window} hours' "
            "ORDER BY mag DESC LIMIT 1"
        )
    if "sismo mas fuerte" in combined or "evento mas fuerte" in combined:
        return (
            "SELECT id, mag, place, event_time FROM curated.events "
            f"WHERE event_time >= now() - interval '{window} hours' "
            "ORDER BY mag DESC LIMIT 1"
        )
    if "magnitud" in combined and any(
        term in normalized for term in ("promedio", "media")
    ):
        return (
            "SELECT round(avg(mag), 2) AS magnitud_promedio FROM curated.events "
            f"WHERE event_time >= now() - interval '{window} hours'"
        )
    if "profund" in normalized and any(
        term in normalized for term in ("maxima", "mayor", "mas profundo")
    ):
        return (
            "SELECT id, depth_km, mag, place, event_time FROM curated.events "
            f"WHERE event_time >= now() - interval '{window} hours' "
            "ORDER BY depth_km DESC LIMIT 1"
        )
    if any(term in normalized for term in ("significativo", "significativos")):
        return (
            "SELECT count(*) AS eventos_significativos FROM curated.events "
            f"WHERE significant = true AND event_time >= now() - interval '{window} hours'"
        )
    if any(term in normalized for term in ("cuantos", "cuantas", "numero", "total")) and any(
        term in combined for term in ("sismo", "evento", "terremoto")
    ):
        return (
            "SELECT count(*) AS eventos FROM curated.events "
            f"WHERE event_time >= now() - interval '{window} hours'"
        )
    if any(term in normalized for term in ("donde", "ubicacion", "lugar", "epicentro")):
        return (
            "SELECT id, place, region, mag, event_time FROM curated.events "
            f"WHERE event_time >= now() - interval '{window} hours' "
            "ORDER BY event_time DESC LIMIT 10"
        )
    if any(term in normalized for term in ("ultimos", "ultimas", "recientes", "ultimo")):
        limit = extract_requested_limit(question)
        window_filter = ""
        if any(term in normalized for term in ("hora", "horas", "dia", "dias", "semana", "mes")):
            window_filter = f"WHERE event_time >= now() - interval '{window} hours' "
        return (
            "SELECT id, mag, place, region, event_time FROM curated.events "
            f"{window_filter}ORDER BY event_time DESC LIMIT {limit}"
        )
    return None


def _clean_sql(sql):
    cleaned = (sql or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("sql"):
            cleaned = cleaned[3:]
    cleaned = cleaned.strip()
    while cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()
    return cleaned


def generate_sql(question, history_text):
    if not settings.ai_enabled:
        return fallback_sql(question, history_text), "", "reglas"
    prompt = (
        PROMPT_PATH.read_text(encoding="utf-8")
        .replace("{{HISTORY}}", history_text)
        .replace("{{QUESTION}}", sanitize_question(question))
    )
    try:
        response = requests.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0, "num_predict": 300},
            },
            timeout=settings.llm_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("response", "")
        start = content.find("{")
        end = content.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Respuesta sin JSON")
        data = json.loads(content[start : end + 1])
        sql = _clean_sql(data.get("sql"))
        if sql:
            return sql, data.get("explanation", ""), "ollama"
    except (requests.RequestException, ValueError, KeyError):
        pass
    return fallback_sql(question, history_text), "", "reglas"


def validate_sql(sql):
    if not isinstance(sql, str) or not sql.strip():
        raise ValueError("SQL vacio")
    cleaned = _clean_sql(sql)
    lowered = cleaned.lower()
    if ";" in cleaned:
        raise ValueError("No se permiten multiples sentencias")
    if any(token in lowered for token in BANNED_TOKENS):
        raise ValueError("El SQL contiene elementos no permitidos")
    try:
        expression = parse_one(cleaned, read="postgres")
    except ParseError as exc:
        raise ValueError("El SQL no es valido") from exc
    if not isinstance(expression, exp.Select):
        raise ValueError("Solo se permiten consultas SELECT")
    cte_names = {cte.alias_or_name.lower() for cte in expression.find_all(exp.CTE)}
    for table in expression.find_all(exp.Table):
        schema = (table.db or "").lower()
        name = table.name.lower()
        if not schema and name in cte_names:
            continue
        if schema != "curated" or name != "events":
            raise ValueError("Solo se permite consultar curated.events")
    limit_node = expression.args.get("limit")
    current_limit = None
    if limit_node is not None:
        try:
            current_limit = int(limit_node.expression.this)
        except (AttributeError, TypeError, ValueError):
            current_limit = None
    if current_limit is not None and current_limit <= MAX_ROWS:
        return expression.sql(dialect="postgres")
    return expression.limit(MAX_ROWS).sql(dialect="postgres")


def execute_sql(db, sql):
    db.execute(text("SET LOCAL statement_timeout = '5000ms'"))
    db.execute(text("SET LOCAL transaction_read_only = on"))
    result = db.execute(text(sql))
    columns = list(result.keys())
    rows = [row_to_dict(dict(zip(columns, row))) for row in result.fetchmany(MAX_ROWS)]
    db.rollback()
    return columns, rows


def log_query(question, sql, provider, success, latency_ms):
    try:
        with reader_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO ai.query_log (question, sql, provider, success, latency_ms)
                    VALUES (:question, :sql, :provider, :success, :latency_ms)
                    """
                ),
                {
                    "question": question,
                    "sql": sql,
                    "provider": provider,
                    "success": success,
                    "latency_ms": latency_ms,
                },
            )
    except Exception:
        pass


def _response(question, answer, answer_provider="reglas", intent=None, **extra):
    payload = {
        "question": question,
        "answer": answer,
        "answer_provider": answer_provider,
        "intent": intent,
        "sql": None,
        "explanation": "",
        "columns": [],
        "rows": [],
        "row_count": 0,
        "provider": "reglas",
        "validated": True,
    }
    payload.update(extra)
    return payload


def ask(question, db, history=None):
    started = time.perf_counter()
    clean_question = sanitize_question(question)
    history_text = format_history(history)

    intent = detect_intent(clean_question)
    if intent:
        return _response(
            clean_question,
            intent["answer"],
            answer_provider="reglas",
            intent=intent["intent"],
        )

    provider = "reglas"
    sql = None
    try:
        deterministic_sql = fallback_sql(clean_question, history_text)
        if deterministic_sql:
            sql = deterministic_sql
            explanation = "Consulta determinista validada sobre curated.events."
        else:
            sql, explanation, provider = generate_sql(clean_question, history_text)
        if not sql:
            log_query(
                clean_question,
                None,
                provider,
                False,
                int((time.perf_counter() - started) * 1000),
            )
            return _response(
                clean_question,
                UNKNOWN_ANSWER,
                answer_provider="reglas",
                intent="desconocido",
            )
        try:
            safe_sql = validate_sql(sql)
        except ValueError:
            fallback = fallback_sql(clean_question, history_text)
            if not fallback:
                raise
            safe_sql = validate_sql(fallback)
            sql = fallback
            provider = "reglas"
            explanation = "Consulta de respaldo validada sobre curated.events."
        columns, rows = execute_sql(db, safe_sql)
        answer, answer_provider = generate_answer(
            clean_question, columns, rows, history_text
        )
        log_query(
            clean_question,
            safe_sql,
            provider,
            True,
            int((time.perf_counter() - started) * 1000),
        )
        return {
            "question": clean_question,
            "answer": answer,
            "answer_provider": answer_provider,
            "intent": "consulta",
            "sql": safe_sql,
            "explanation": explanation,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "provider": provider,
            "validated": True,
        }
    except ValueError as exc:
        db.rollback()
        log_query(
            clean_question,
            sql,
            provider,
            False,
            int((time.perf_counter() - started) * 1000),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        log_query(
            clean_question,
            sql,
            provider,
            False,
            int((time.perf_counter() - started) * 1000),
        )
        raise HTTPException(
            status_code=400, detail="La consulta generada no pudo ejecutarse"
        ) from exc
