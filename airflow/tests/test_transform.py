from datetime import datetime, timezone

from include.transform import map_feature, region_from_place, validate_event


def feature(**overrides):
    data = {
        "id": "us7000test",
        "properties": {
            "mag": 4.8,
            "place": "10 km NE of Lima, Peru",
            "time": int(datetime.now(timezone.utc).timestamp() * 1000),
            "updated": int(datetime.now(timezone.utc).timestamp() * 1000),
            "tsunami": 0,
            "sig": 350,
            "status": "reviewed",
            "magType": "ml",
            "type": "earthquake",
            "url": "https://example.test/event",
        },
        "geometry": {"coordinates": [-77.03, -12.05, 35.0]},
    }
    for key, value in overrides.items():
        if key in data["properties"]:
            data["properties"][key] = value
        else:
            data[key] = value
    return data


def test_map_feature_builds_expected_row():
    row = map_feature(feature())
    assert row["id"] == "us7000test"
    assert row["mag"] == 4.8
    assert row["region"] == "Lima, Peru"
    assert row["longitude"] == -77.03
    assert row["latitude"] == -12.05
    assert row["depth_km"] == 35.0
    assert row["hour_bucket"].minute == 0
    assert validate_event(row) == []


def test_validate_event_rejects_invalid_coordinates_and_magnitude():
    row = map_feature(feature(mag=12.0))
    row["latitude"] = 120.0
    row["longitude"] = -250.0
    row["depth_km"] = -4
    reasons = validate_event(row)
    assert "magnitud_fuera_de_rango" in reasons
    assert "latitud_fuera_de_rango" in reasons
    assert "longitud_fuera_de_rango" in reasons
    assert "profundidad_fuera_de_rango" in reasons


def test_validate_event_rejects_missing_magnitude():
    row = map_feature(feature())
    row["mag"] = None
    assert "magnitud_ausente" in validate_event(row)


def test_region_from_place():
    assert region_from_place("South of the Fiji Islands") == "Fiji Islands"
    assert region_from_place("Central Alaska") == "Central Alaska"
    assert region_from_place("") == "Sin region"
