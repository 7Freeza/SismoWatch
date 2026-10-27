from app.natural_answer import (
    answer_includes_required_values,
    answer_numbers_match,
    answer_places_match,
    fallback_answer,
)


def test_count_answer_is_natural():
    answer = fallback_answer(
        "Cuantos sismos hubo?",
        ["eventos"],
        [{"eventos": 25}],
    )
    assert "25" in answer
    assert "id=" not in answer


def test_single_event_answer_uses_places_and_magnitude():
    answer = fallback_answer(
        "Cual fue el sismo mas fuerte?",
        ["id", "mag", "place", "event_time"],
        [
            {
                "id": "us6000u43g",
                "mag": 7.0,
                "place": "191 km ENE of Nagqu, China",
                "event_time": "2026-10-22T14:33:40+00:00",
            }
        ],
    )
    assert "Nagqu" in answer
    assert "7" in answer
    assert "id=" not in answer


def test_regions_answer_summarizes_top_three():
    answer = fallback_answer(
        "Que regiones tienen mas actividad?",
        ["region", "eventos"],
        [
            {"region": "Adak, Alaska", "eventos": 84},
            {"region": "Port-Olry, Vanuatu", "eventos": 77},
            {"region": "Tadine, New Caledonia", "eventos": 45},
            {"region": "Atka, Alaska", "eventos": 30},
        ],
    )
    assert "Adak, Alaska" in answer
    assert "84" in answer
    assert "Atka" not in answer


def test_empty_result_is_natural():
    answer = fallback_answer("Cuantos sismos hubo?", ["eventos"], [])
    assert "No encontré" in answer


def test_answer_numbers_are_checked_against_rows():
    rows = [{"mag": 7.0, "place": "Nagqu, China"}]
    assert answer_numbers_match("El sismo fue de magnitud 7 en Nagqu.", rows, "magnitud")
    assert not answer_numbers_match("El sismo fue de magnitud 9 en Nagqu.", rows, "magnitud")


def test_place_validation_rejects_invented_location():
    rows = [{"place": "191 km ENE of Nagqu, China", "mag": 7.0}]
    assert answer_places_match("El sismo fue en Nagqu, China.", rows)
    assert not answer_places_match("El sismo fue en San Francisco, California.", rows)


def test_count_answer_must_include_the_count():
    rows = [{"eventos": 34}]
    assert answer_includes_required_values("Se registraron 34 eventos.", rows, "cuantos sismos")
    assert not answer_includes_required_values("No tengo acceso a esos datos.", rows, "cuantos sismos")


def test_regions_answer_must_include_top_count():
    rows = [
        {"region": "Port-Olry, Vanuatu", "eventos": 56},
        {"region": "Nagqu, China", "eventos": 22},
    ]
    assert not answer_includes_required_values(
        "Las regiones mas activas son Port-Olry y Nagqu.", rows, "regiones"
    )
    assert answer_includes_required_values(
        "Port-Olry lidera con 56 eventos y Nagqu suma 22.", rows, "regiones"
    )
