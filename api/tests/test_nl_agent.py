import pytest

from app.nl_agent import validate_sql


def test_validator_accepts_curated_select_and_adds_limit():
    sql = validate_sql("SELECT region, count(*) AS eventos FROM curated.events GROUP BY region")
    assert "curated.events" in sql
    assert "LIMIT 200" in sql.upper()


def test_validator_preserves_small_limit():
    sql = validate_sql("SELECT id, mag FROM curated.events ORDER BY mag DESC LIMIT 1")
    assert "LIMIT 1" in sql.upper()
    assert "LIMIT 200" not in sql.upper()


def test_validator_accepts_cte_over_curated():
    sql = validate_sql(
        "WITH recent AS (SELECT * FROM curated.events) SELECT count(*) FROM recent"
    )
    assert "curated.events" in sql


def test_validator_rejects_cte_over_other_schema():
    with pytest.raises(ValueError):
        validate_sql("WITH recent AS (SELECT * FROM raw.events) SELECT count(*) FROM recent")


def test_validator_rejects_dml():
    with pytest.raises(ValueError):
        validate_sql("DELETE FROM curated.events")


def test_validator_rejects_other_schemas():
    with pytest.raises(ValueError):
        validate_sql("SELECT * FROM raw.events")


def test_validator_rejects_multiple_statements():
    with pytest.raises(ValueError):
        validate_sql("SELECT * FROM curated.events; DROP TABLE curated.events")


def test_count_fallback_beats_recent_events():
    from app.nl_agent import fallback_sql

    sql = fallback_sql("Cuantos sismos se registraron en las ultimas 24 horas?")
    assert "count(*)" in sql.lower()


def test_regions_fallback_uses_group_by():
    from app.nl_agent import fallback_sql

    sql = fallback_sql("Que regiones tienen mas actividad en los ultimos 7 dias?")
    assert "group by region" in sql.lower()


def test_recent_events_respect_requested_limit():
    from app.nl_agent import fallback_sql

    assert "LIMIT 3" in fallback_sql("ultimos 3 terremotos")
    assert "LIMIT 10" in fallback_sql("muestrame los ultimos 10 sismos")
    sql = fallback_sql("muestrame sismos de las ultimas 2 horas")
    assert "LIMIT 10" in sql
    assert "interval '2 hours'" in sql
