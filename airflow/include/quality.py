from collections import Counter

from include.transform import map_feature, validate_event

MAX_REJECTION_RATE = 0.2
MAX_VOLUME = 20000

RULES = [
    {
        "name": "esquema_y_tipos",
        "description": "id, time, coordenadas, magnitud, tipo y metadatos con tipos esperados",
    },
    {
        "name": "campos_obligatorios",
        "description": "id, event_time, place, latitud, longitud, profundidad y tipo presentes",
    },
    {
        "name": "rangos_geograficos",
        "description": "latitud entre -90 y 90, longitud entre -180 y 180",
    },
    {
        "name": "rangos_fisicos",
        "description": "magnitud entre -1.5 y 10.5, profundidad entre 0 y 800 km",
    },
    {
        "name": "fechas_plausibles",
        "description": "fecha valida, no futura y posterior a 1900",
    },
    {
        "name": "texto_sanitizado",
        "description": "place sin caracteres de control y con longitud maxima de 300",
    },
    {
        "name": "unicidad_id",
        "description": "el id de evento es unico y se publica con upsert",
    },
    {
        "name": "volumen_plausible",
        "description": f"el lote contiene entre 1 y {MAX_VOLUME} registros",
    },
]


def evaluate(features):
    valid = []
    rejects = []
    for feature in features:
        row = map_feature(feature)
        reasons = validate_event(row)
        if reasons:
            rejects.append(
                {
                    "event_id": row.get("id") or None,
                    "payload": feature,
                    "reasons": reasons,
                }
            )
        else:
            valid.append(row)
    return valid, rejects


def build_metrics(total, passed, rejected, rejects):
    score = round((passed / total) * 100, 2) if total else 0.0
    rejection_rate = round((rejected / total), 4) if total else 0.0
    gate_passed = (
        total > 0
        and total <= MAX_VOLUME
        and passed > 0
        and rejection_rate <= MAX_REJECTION_RATE
    )
    reason_counts = Counter(
        reason for reject in rejects for reason in reject.get("reasons", [])
    )
    details = {
        "rejection_rate": rejection_rate,
        "max_rejection_rate": MAX_REJECTION_RATE,
        "volume_min": 1,
        "volume_max": MAX_VOLUME,
        "reason_counts": dict(reason_counts),
    }
    return {
        "total": total,
        "passed": passed,
        "rejected": rejected,
        "score": score,
        "gate_passed": gate_passed,
        "rules": RULES,
        "details": details,
    }
