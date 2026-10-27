from datetime import datetime, timezone

from include.quality import build_metrics, evaluate


def feature(event_id, mag, latitude, longitude):
    return {
        "id": event_id,
        "properties": {
            "mag": mag,
            "place": "Test region",
            "time": int(datetime.now(timezone.utc).timestamp() * 1000),
            "updated": int(datetime.now(timezone.utc).timestamp() * 1000),
            "tsunami": 0,
            "sig": 100,
            "status": "reviewed",
            "magType": "ml",
            "type": "earthquake",
            "url": "https://example.test/event",
        },
        "geometry": {"coordinates": [longitude, latitude, 10.0]},
    }


def test_evaluate_separates_valid_and_invalid_events():
    valid, rejects = evaluate(
        [
            feature("ok-1", 3.2, 10.0, -70.0),
            feature("bad-1", 44.0, 10.0, -70.0),
            feature("bad-2", 3.0, 120.0, -70.0),
        ]
    )
    assert len(valid) == 1
    assert len(rejects) == 2
    assert "magnitud_fuera_de_rango" in rejects[0]["reasons"]
    assert "latitud_fuera_de_rango" in rejects[1]["reasons"]


def test_quality_gate_rejects_when_too_many_invalid_rows():
    valid, rejects = evaluate(
        [
            feature("ok-1", 3.2, 10.0, -70.0),
            feature("bad-1", 44.0, 10.0, -70.0),
            feature("bad-2", 3.0, 120.0, -70.0),
        ]
    )
    metrics = build_metrics(3, len(valid), len(rejects), rejects)
    assert metrics["score"] == 33.33
    assert metrics["gate_passed"] is False


def test_quality_gate_passes_with_all_valid_rows():
    valid, rejects = evaluate([feature("ok-1", 3.2, 10.0, -70.0)])
    metrics = build_metrics(1, len(valid), len(rejects), rejects)
    assert metrics["score"] == 100.0
    assert metrics["gate_passed"] is True
