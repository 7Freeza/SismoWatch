from include.ai import numbers_match, statements_match

STATS = {
    "events_24h": 26,
    "events_previous_24h": 39,
    "max_magnitude": 5.2,
    "avg_magnitude": 3.05,
    "tsunami_events": 0,
    "significant_events": 10,
    "anomalies_24h": 2,
    "quality_score": 99.49,
    "top_regions": [{"region": "Port-Olry, Vanuatu", "events": 2}],
    "strongest_event": {
        "mag": 5.2,
        "place": "Port-Olry, Vanuatu",
        "event_time": "2026-10-26T12:13:30+00:00",
    },
}


def test_numbers_match_accepts_known_values():
    text = "Se registraron 26 eventos con magnitud maxima 5.2 y calidad 99.49."
    assert numbers_match(text, STATS) is True


def test_numbers_match_rejects_invented_value():
    assert numbers_match("Se registraron 977 eventos.", STATS) is False


def test_statements_match_rejects_false_absence():
    assert statements_match("No hubo eventos significativos.", STATS) is False


def test_statements_match_rejects_wrong_comparison_direction():
    assert statements_match("Los 26 eventos superando los 39 previos.", STATS) is False


def test_statements_match_accepts_correct_claims():
    text = (
        "Hubo 10 eventos significativos y 26 eventos en total. "
        "La actividad descendio frente a los 39 previos."
    )
    assert statements_match(text, STATS) is True
