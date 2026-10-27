from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.airflow_client import trigger_dag
from app.db import get_db
from app.schemas import BackfillRequest, RegenerateRequest
from app.serializers import row_to_dict
from app.security import require_admin

router = APIRouter(prefix="/api", tags=["administracion"])


@router.post("/admin/backfill")
def launch_backfill(payload: BackfillRequest, user=Depends(require_admin)):
    return trigger_dag(
        "backfill_usgs",
        {"days": payload.days, "minmagnitude": 2.5},
    )


@router.post("/admin/reports/regenerate")
def regenerate_report(payload: RegenerateRequest, user=Depends(require_admin)):
    return trigger_dag("daily_ai", {"reason": payload.reason})


@router.get("/admin/ai-runs")
def ai_runs(
    limit: int = Query(default=20, ge=1, le=100),
    user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = (
        db.execute(
            text(
                """
                SELECT id, kind, model, prompt_version, tokens_in, tokens_out,
                       latency_ms, cost_estimate, success, error, created_at
                FROM ai.runs
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        .mappings()
        .all()
    )
    return [row_to_dict(row) for row in rows]
