from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db
from app.serializers import clean_value, row_to_dict
from app.security import require_viewer

router = APIRouter(prefix="/api", tags=["pipeline"])


@router.get("/pipeline/status")
def pipeline_status(user=Depends(require_viewer), db: Session = Depends(get_db)):
    runs = (
        db.execute(
            text(
                """
                SELECT DISTINCT ON (dag_id)
                    dag_id, run_id, status, started_at, finished_at, message, details
                FROM pipeline.runs
                ORDER BY dag_id, started_at DESC
                """
            )
        )
        .mappings()
        .all()
    )
    quality = (
        db.execute(
            text(
                """
                SELECT dag_run_id, checked_at, total, passed, rejected, score,
                       gate_passed, rules, details
                FROM quality.metrics
                ORDER BY checked_at DESC
                LIMIT 1
                """
            )
        )
        .mappings()
        .first()
    )
    last_update = quality["checked_at"] if quality else None
    anomalies = (
        db.execute(
            text(
                """
                SELECT id, detected_at, window_start, window_end, method, score,
                       event_count, expected, severity, explanation
                FROM ai.anomalies
                ORDER BY window_start DESC
                LIMIT 5
                """
            )
        )
        .mappings()
        .all()
    )
    freshness = None
    if last_update is not None:
        freshness = max(
            0, int((datetime.now(timezone.utc) - last_update).total_seconds())
        )
    quality_data = row_to_dict(quality) if quality else None
    if quality_data and user.get("role") != "admin":
        quality_data.pop("rules", None)
        quality_data.pop("details", None)
    result = {
        "runs": [row_to_dict(row) for row in runs],
        "quality": quality_data,
        "freshness_seconds": freshness,
        "last_update": clean_value(last_update),
        "anomalies": [row_to_dict(row) for row in anomalies],
    }
    if user.get("role") == "admin":
        history = (
            db.execute(
                text(
                    """
                    SELECT dag_run_id, checked_at, total, passed, rejected, score,
                           gate_passed, details
                    FROM quality.metrics
                    ORDER BY checked_at DESC
                    LIMIT 10
                    """
                )
            )
            .mappings()
            .all()
        )
        run_history = (
            db.execute(
                text(
                    """
                    SELECT dag_id, run_id, status, started_at, finished_at, message
                    FROM pipeline.runs
                    ORDER BY started_at DESC
                    LIMIT 30
                    """
                )
            )
            .mappings()
            .all()
        )
        result["quality_history"] = [row_to_dict(row) for row in history]
        result["run_history"] = [row_to_dict(row) for row in run_history]
    return result
