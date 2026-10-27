import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.config import settings
from app.text_utils import extract_numbers, normalize_text, sanitize_text

PROMPT_VERSION = "answer_v1"
PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / f"{PROMPT_VERSION}.txt"
MAX_PROMPT_ROWS = 15
MONTHS = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
COUNT_KEYS = {
    "total",
    "count",
    "eventos",
    "eventos_24h",
    "eventos_con_tsunami",
    "eventos_significativos",
    "magnitud_promedio",
    "anomalias",
    "filas",
    "sismo_count",
}
NO_DATA_PATTERN = re.compile(
    r"no se encontr|no hay registros|no hay sismos|no hay eventos|no hay datos|no hay resultados|sin resultados|sin eventos|no hubo|ningun evento|ninguna coincidencia",
    re.IGNORECASE,
)
PLACE_PATTERN = re.compile(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*")
PLACE_STOPWORDS = {
    "el",
    "la",
    "los",
    "las",
    "un",
    "una",
    "unos",
    "unas",
    "en",
    "se",
    "no",
    "si",
    "es",
    "son",
    "fue",
    "hubo",
    "hay",
    "este",
    "esta",
    "estos",
    "estas",
    "ese",
    "esa",
    "para",
    "por",
    "con",
    "del",
    "de",
    "al",
    "a",
    "y",
    "o",
    "que",
    "cual",
    "cuando",
    "donde",
    "como",
    "hoy",
    "ayer",
    "durante",
    "entre",
    "segun",
    "ademas",
    "tambien",
    "mientras",
    "sismowatch",
    "superapp",
    "sismo",
    "sismos",
    "evento",
    "eventos",
    "region",
    "regiones",
    "magnitud",
    "actividad",
    "ultimas",
    "ultimos",
    "ultima",
    "ultimo",
}


def _format_number(value):
    if isinstance(value, bool):
        return "si" if value else "no"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _format_date(value):
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return str(value)
    return (
        f"{moment.day} de {MONTHS[moment.month - 1]} de {moment.year} "
        f"a las {moment.hour:02d}:{moment.minute:02d} UTC"
    )


def _describe_row(row):
    parts = []
    if row.get("place"):
        parts.append(f"en {row['place']}")
    elif row.get("region"):
        parts.append(f"en {row['region']}")
    if row.get("mag") is not None:
        parts.append(f"con magnitud {_format_number(row['mag'])}")
    if row.get("depth_km") is not None:
        parts.append(f"a {_format_number(row['depth_km'])} km de profundidad")
    if row.get("event_time"):
        parts.append(f"el {_format_date(row['event_time'])}")
    if row.get("tsunami"):
        parts.append("con alerta de tsunami")
    if not parts:
        if row.get("id"):
            parts.append(f"para el evento {row['id']}")
        if row.get("latitude") is not None and row.get("longitude") is not None:
            parts.append(
                f"en las coordenadas {row['latitude']}, {row['longitude']}"
            )
    if not parts:
        return "Hay un resultado disponible."
    return "El evento " + " ".join(parts) + "."


def _count_sentence(key, value):
    label = _format_number(value)
    lowered = key.lower()
    if "tsunami" in lowered:
        return f"Se registraron {label} eventos con alerta de tsunami."
    if "significativo" in lowered:
        return f"Se registraron {label} eventos significativos."
    if "magnitud" in lowered:
        return f"La magnitud promedio es {label}."
    if "anomalia" in lowered:
        return f"Se detectaron {label} anomalías."
    if "total" in lowered or "count" in lowered or "evento" in lowered or "sismo" in lowered:
        return f"Se registraron {label} eventos."
    return f"El resultado es {label}."


def fallback_answer(question, columns, rows):
    if not rows:
        return "No encontré eventos que coincidan con esa consulta."
    if len(rows) == 1:
        row = rows[0]
        if len(columns) == 1:
            key = columns[0]
            value = row.get(key)
            if key.lower() in COUNT_KEYS or "count" in key.lower():
                return _count_sentence(key, value)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return _count_sentence("total", value)
            if "magnitud" in key.lower():
                return f"La magnitud es {_format_number(value)}."
        return _describe_row(row)
    if "region" in columns and any(
        "count" in column.lower() or column.lower() in {"eventos", "total"} for column in columns
    ):
        count_column = next(
            column
            for column in columns
            if "count" in column.lower() or column.lower() in {"eventos", "total"}
        )
        ordered = sorted(rows, key=lambda row: float(row.get(count_column) or 0), reverse=True)
        parts = [
            f"{row.get('region')} ({_format_number(row.get(count_column))})"
            for row in ordered[:3]
        ]
        return "Las regiones con más actividad fueron " + ", ".join(parts) + "."
    if "place" in columns:
        described = [_describe_row(row) for row in rows[:3]]
        return "Los eventos más relevantes fueron: " + " ".join(described)
    described = [_describe_row(row) for row in rows[:3]]
    suffix = "" if len(rows) <= 3 else f" Hay {len(rows)} resultados en total."
    return "Encontré varios resultados. " + " ".join(described) + suffix


def _allowed_numbers(rows, question):
    allowed = {float(len(rows))}

    def add(value):
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            allowed.add(round(float(value), 4))
        elif isinstance(value, str):
            for number in extract_numbers(value):
                allowed.add(round(number, 4))
            try:
                moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return
            allowed.update(
                {
                    float(moment.year),
                    float(moment.month),
                    float(moment.day),
                    float(moment.hour),
                    float(moment.minute),
                }
            )
        elif isinstance(value, dict):
            for item in value.values():
                add(item)
        elif isinstance(value, list):
            for item in value:
                add(item)

    for row in rows:
        for key, value in row.items():
            if key in {"id", "url"}:
                continue
            add(value)
    for number in extract_numbers(question):
        allowed.add(round(number, 4))
    now = datetime.now(timezone.utc)
    allowed.update({float(now.year), float(now.month), float(now.day)})
    for value in list(allowed):
        allowed.add(round(value, 0))
        allowed.add(round(value, 1))
        allowed.add(round(value, 2))
    return allowed


def answer_numbers_match(answer, rows, question):
    allowed = _allowed_numbers(rows, question)
    for number in extract_numbers(answer):
        if not any(
            abs(number - candidate) <= max(0.01, abs(candidate) * 0.01)
            for candidate in allowed
        ):
            return False
    return True


def answer_includes_required_values(answer, rows, question):
    if not rows:
        return True
    if len(rows) > 1:
        columns = {key.lower() for key in rows[0]}
        if "region" in columns:
            count_key = next(
                (
                    key
                    for key in rows[0]
                    if key.lower() in COUNT_KEYS or "count" in key.lower()
                ),
                None,
            )
            if count_key:
                top = max(rows, key=lambda row: float(row.get(count_key) or 0))
                target = float(top[count_key])
                numbers = extract_numbers(answer)
                return any(
                    abs(number - target) <= max(0.01, abs(target) * 0.01)
                    for number in numbers
                )
        return True
    row = rows[0]
    required = []
    for key in row:
        if key.lower() in COUNT_KEYS or "count" in key.lower():
            required.append(key)
    normalized = normalize_text(question)
    if "magnitud" in normalized and "mag" in row:
        required.append("mag")
    if "profund" in normalized and "depth_km" in row:
        required.append("depth_km")
    numbers = extract_numbers(answer)
    for key in required:
        value = row.get(key)
        if isinstance(value, bool):
            continue
        try:
            target = float(value)
        except (TypeError, ValueError):
            continue
        if not any(abs(number - target) <= max(0.01, abs(target) * 0.01) for number in numbers):
            return False
    return True


def answer_places_match(answer, rows):
    places = normalize_text(
        " ".join(f"{row.get('place', '')} {row.get('region', '')}" for row in rows)
    )
    if not places.strip():
        return True
    for match in PLACE_PATTERN.findall(answer):
        if normalize_text(match.split()[0]) in PLACE_STOPWORDS:
            continue
        if normalize_text(match) not in places:
            return False
    return True


def _clean_answer(value):
    text = (value or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
    text = re.sub(r"\s+", " ", text).strip().strip('"').strip("'")
    text = re.sub(r"\beventos sismos\b", "eventos sísmicos", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsismos eventos\b", "eventos sísmicos", text, flags=re.IGNORECASE)
    if text.lower().startswith("respuesta:"):
        text = text[10:].strip()
    return sanitize_text(text, 700)


def generate_answer(question, columns, rows, history_text):
    fallback = fallback_answer(question, columns, rows)
    if not rows:
        return fallback, "reglas"
    normalized = normalize_text(question)
    if len(rows) > 1 and any(
        term in normalized
        for term in (
            "donde",
            "ubicacion",
            "lugar",
            "epicentro",
            "ultimo",
            "ultimos",
            "ultima",
            "ultimas",
            "reciente",
            "recientes",
        )
    ):
        return fallback, "reglas"
    prompt = (
        PROMPT_PATH.read_text(encoding="utf-8")
        .replace("{{HISTORY}}", history_text)
        .replace("{{QUESTION}}", sanitize_text(question, 500))
        .replace("{{COLUMNS}}", json.dumps(columns, ensure_ascii=False))
        .replace(
            "{{ROWS}}",
            json.dumps(rows[:MAX_PROMPT_ROWS], ensure_ascii=False, default=str),
        )
    )
    try:
        response = requests.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": settings.answer_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 180},
            },
            timeout=20,
        )
        response.raise_for_status()
        answer = _clean_answer(response.json().get("response", ""))
        if not answer or len(answer) < 8:
            return fallback, "reglas"
        if NO_DATA_PATTERN.search(answer):
            return fallback, "reglas"
        if not answer_numbers_match(answer, rows, question):
            return fallback, "reglas"
        if not answer_places_match(answer, rows):
            return fallback, "reglas"
        if not answer_includes_required_values(answer, rows, question):
            return fallback, "reglas"
        return answer, "ollama"
    except (requests.RequestException, ValueError, KeyError):
        return fallback, "reglas"
