import re
from datetime import datetime, timedelta, timezone


def as_float(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sanitize_text(value, max_length=300):
    if value is None:
        return ""
    text = str(value)
    text = "".join(ch for ch in text if ch == " " or ch.isprintable())
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length]


def region_from_place(place):
    text = sanitize_text(place)
    if not text:
        return "Sin region"
    lowered = text.lower()
    region = text.rsplit(" of ", 1)[-1] if " of " in lowered else text
    region = re.sub(r"^(the|an?)\s+", "", region, flags=re.IGNORECASE)
    region = region.strip(" .,")
    return region[:120] or "Sin region"


def epoch_to_datetime(value):
    millis = as_float(value)
    if millis is None:
        return None
    try:
        return datetime.fromtimestamp(millis / 1000.0, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def map_feature(feature):
    properties = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []
    longitude = as_float(coordinates[0]) if len(coordinates) > 0 else None
    latitude = as_float(coordinates[1]) if len(coordinates) > 1 else None
    depth_km = as_float(coordinates[2]) if len(coordinates) > 2 else None
    event_time = epoch_to_datetime(properties.get("time"))
    updated_time = epoch_to_datetime(properties.get("updated"))
    tsunami = properties.get("tsunami")
    significance = properties.get("sig")
    return {
        "id": sanitize_text(feature.get("id"), 80),
        "mag": as_float(properties.get("mag")),
        "place": sanitize_text(properties.get("place")),
        "region": region_from_place(properties.get("place")),
        "event_time": event_time,
        "updated_time": updated_time,
        "tsunami": bool(tsunami) if tsunami is not None else None,
        "significance": int(significance) if significance is not None else None,
        "status": sanitize_text(properties.get("status"), 40),
        "mag_type": sanitize_text(properties.get("magType"), 20),
        "event_type": sanitize_text(properties.get("type"), 40) or "unknown",
        "url": sanitize_text(properties.get("url"), 500),
        "longitude": longitude,
        "latitude": latitude,
        "depth_km": depth_km,
        "hour_bucket": event_time.replace(minute=0, second=0, microsecond=0)
        if event_time
        else None,
    }


def validate_event(row):
    reasons = []
    if not row.get("id"):
        reasons.append("id_invalido")
    magnitude = row.get("mag")
    if magnitude is None:
        reasons.append("magnitud_ausente")
    elif not -1.5 <= magnitude <= 10.5:
        reasons.append("magnitud_fuera_de_rango")
    if not row.get("place"):
        reasons.append("lugar_ausente")
    longitude = row.get("longitude")
    if longitude is None or not -180.0 <= longitude <= 180.0:
        reasons.append("longitud_fuera_de_rango")
    latitude = row.get("latitude")
    if latitude is None or not -90.0 <= latitude <= 90.0:
        reasons.append("latitud_fuera_de_rango")
    depth = row.get("depth_km")
    if depth is None or not 0.0 <= depth <= 800.0:
        reasons.append("profundidad_fuera_de_rango")
    event_time = row.get("event_time")
    if event_time is None:
        reasons.append("fecha_invalida")
    else:
        now = datetime.now(timezone.utc)
        if event_time > now + timedelta(days=1):
            reasons.append("fecha_futura")
        if event_time.year < 1900:
            reasons.append("fecha_antigua")
    if not row.get("event_type"):
        reasons.append("tipo_ausente")
    if len(row.get("place", "")) > 300:
        reasons.append("lugar_demasiado_largo")
    return reasons
