from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.serializers import clean_value, row_to_dict
from app.security import require_viewer

router = APIRouter(prefix="/api", tags=["eventos"])

SORT_COLUMNS = {"event_time": "event_time", "mag": "mag", "significance": "significance"}


def build_filters(start, end, min_magnitude, region, search, event_type):
    clauses = []
    params = {}
    if start is not None:
        clauses.append("event_time >= :start")
        params["start"] = start
    if end is not None:
        clauses.append("event_time <= :end")
        params["end"] = end
    if min_magnitude is not None:
        clauses.append("mag >= :min_magnitude")
        params["min_magnitude"] = min_magnitude
    if region:
        clauses.append("region = :region")
        params["region"] = region
    if event_type:
        clauses.append("event_type = :event_type")
        params["event_type"] = event_type
    if search:
        clauses.append("(place ILIKE :search OR region ILIKE :search)")
        params["search"] = f"%{search}%"
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


@router.get("/events")
def list_events(
    start: datetime | None = None,
    end: datetime | None = None,
    min_magnitude: float | None = Query(default=None, ge=-1.5, le=10.5),
    region: str | None = Query(default=None, max_length=120),
    q: str | None = Query(default=None, max_length=120),
    event_type: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="event_time"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    user=Depends(require_viewer),
    db: Session = Depends(get_db),
):
    if sort not in SORT_COLUMNS:
        raise HTTPException(status_code=422, detail="Columna de orden no permitida")
    where, params = build_filters(start, end, min_magnitude, region, q, event_type)
    total = db.execute(
        text(f"SELECT count(*) FROM curated.events {where}"), params
    ).scalar_one()
    rows = (
        db.execute(
            text(
                f"""
                SELECT
                    id, mag, place, region, event_time, updated_time, tsunami,
                    significance, status, mag_type, event_type, url, longitude,
                    latitude, depth_km, significant, updated_at
                FROM curated.events
                {where}
                ORDER BY {SORT_COLUMNS[sort]} {order.upper()} NULLS LAST, id
                LIMIT :limit OFFSET :offset
                """
            ),
            {**params, "limit": limit, "offset": offset},
        )
        .mappings()
        .all()
    )
    return {
        "items": [row_to_dict(row) for row in rows],
        "total": int(total),
        "limit": limit,
        "offset": offset,
    }


@router.get("/events/{event_id}")
def get_event(event_id: str, user=Depends(require_viewer), db: Session = Depends(get_db)):
    row = (
        db.execute(
            text(
                """
                SELECT
                    id, mag, place, region, event_time, updated_time, tsunami,
                    significance, status, mag_type, event_type, url, longitude,
                    latitude, depth_km, significant, updated_at
                FROM curated.events
                WHERE id = :event_id
                """
            ),
            {"event_id": event_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return row_to_dict(row)
