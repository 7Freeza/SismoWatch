from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.security import require_viewer
from app.serializers import clean_value, row_to_dict

router = APIRouter(prefix="/api", tags=["dashboard"])

MAGNITUDE_ORDER = ["0-1", "1-2", "2-3", "3-4", "4-5", "5-6", "6-7", "7+"]


@router.get("/kpis")
def get_kpis(user=Depends(require_viewer), db: Session = Depends(get_db)):
    row = (
        db.execute(
            text(
                """
                SELECT
                    count(*) FILTER (WHERE event_time >= now() - interval '24 hours') AS events_24h,
                    count(*) FILTER (
                        WHERE event_time >= now() - interval '48 hours'
                          AND event_time < now() - interval '24 hours'
                    ) AS events_previous_24h,
                    COALESCE(max(mag) FILTER (
                        WHERE event_time >= now() - interval '24 hours'
                    ), 0) AS max_magnitude,
                    COALESCE(avg(mag) FILTER (
                        WHERE event_time >= now() - interval '24 hours'
                    ), 0) AS avg_magnitude,
                    count(*) FILTER (
                        WHERE tsunami AND event_time >= now() - interval '24 hours'
                    ) AS tsunami_events,
                    count(*) FILTER (
                        WHERE significant AND event_time >= now() - interval '24 hours'
                    ) AS significant_events,
                    count(*) AS total_events
                FROM curated.events
                """
            )
        )
        .mappings()
        .first()
    )
    quality = (
        db.execute(
            text(
                "SELECT score, checked_at FROM quality.metrics ORDER BY checked_at DESC LIMIT 1"
            )
        )
        .mappings()
        .first()
    )
    anomalies = db.execute(
        text(
            "SELECT count(*) FROM ai.anomalies WHERE detected_at >= now() - interval '24 hours'"
        )
    ).scalar_one()
    last_update = quality["checked_at"] if quality else None
    freshness = None
    if last_update is not None:
        freshness = max(
            0,
            int((datetime.now(timezone.utc) - last_update).total_seconds()),
        )
    return {
        "events_24h": int(row["events_24h"]),
        "events_previous_24h": int(row["events_previous_24h"]),
        "max_magnitude": clean_value(round(float(row["max_magnitude"]), 2)),
        "avg_magnitude": clean_value(round(float(row["avg_magnitude"]), 2)),
        "tsunami_events": int(row["tsunami_events"]),
        "significant_events": int(row["significant_events"]),
        "total_events": int(row["total_events"]),
        "quality_score": clean_value(round(float(quality["score"]), 2)) if quality else 0,
        "quality_checked_at": clean_value(quality["checked_at"]) if quality else None,
        "anomalies_24h": int(anomalies),
        "last_update": clean_value(last_update),
        "freshness_seconds": freshness,
    }


@router.get("/stats/timeseries")
def get_timeseries(
    hours: int = Query(default=24, ge=1, le=168),
    user=Depends(require_viewer),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            text(
                """
                WITH buckets AS (
                    SELECT generate_series(
                        date_trunc('hour', now()) - (:hours - 1) * interval '1 hour',
                        date_trunc('hour', now()),
                        interval '1 hour'
                    ) AS bucket
                )
                SELECT
                    b.bucket,
                    count(e.id) AS events,
                    COALESCE(max(e.mag), 0) AS max_magnitude,
                    COALESCE(avg(e.mag), 0) AS avg_magnitude
                FROM buckets b
                LEFT JOIN curated.events e ON e.hour_bucket = b.bucket
                GROUP BY b.bucket
                ORDER BY b.bucket
                """
            ),
            {"hours": hours},
        )
        .mappings()
        .all()
    )
    return [
        {
            "bucket": clean_value(row["bucket"]),
            "events": int(row["events"]),
            "max_magnitude": clean_value(round(float(row["max_magnitude"]), 2)),
            "avg_magnitude": clean_value(round(float(row["avg_magnitude"]), 2)),
        }
        for row in rows
    ]


@router.get("/stats/regions")
def get_regions(
    days: int = Query(default=30, ge=1, le=90),
    limit: int = Query(default=10, ge=1, le=50),
    user=Depends(require_viewer),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            text(
                """
                SELECT
                    region,
                    count(*) AS events,
                    max(mag) AS max_magnitude,
                    avg(mag) AS avg_magnitude
                FROM curated.events
                WHERE event_time >= now() - (:days * interval '1 day')
                GROUP BY region
                ORDER BY events DESC
                LIMIT :limit
                """
            ),
            {"days": days, "limit": limit},
        )
        .mappings()
        .all()
    )
    return [row_to_dict(row) for row in rows]


@router.get("/stats/magnitude")
def get_magnitude_distribution(
    user=Depends(require_viewer), db: Session = Depends(get_db)
):
    rows = (
        db.execute(
            text(
                """
                SELECT bucket, count(*) AS events
                FROM (
                    SELECT CASE
                        WHEN mag < 1 THEN '0-1'
                        WHEN mag < 2 THEN '1-2'
                        WHEN mag < 3 THEN '2-3'
                        WHEN mag < 4 THEN '3-4'
                        WHEN mag < 5 THEN '4-5'
                        WHEN mag < 6 THEN '5-6'
                        WHEN mag < 7 THEN '6-7'
                        ELSE '7+'
                    END AS bucket
                    FROM curated.events
                    WHERE event_time >= now() - interval '30 days'
                ) labeled
                GROUP BY bucket
                """
            )
        )
        .mappings()
        .all()
    )
    counts = {row["bucket"]: int(row["events"]) for row in rows}
    return [{"bucket": bucket, "events": counts.get(bucket, 0)} for bucket in MAGNITUDE_ORDER]
