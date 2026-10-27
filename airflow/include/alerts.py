import requests

from include.db import record_pipeline_run
from include.settings import ALERT_WEBHOOK_URL


def _run_details(context):
    dag_run = context.get("dag_run")
    details = {}
    if dag_run is not None:
        if dag_run.start_date:
            details["started_at"] = dag_run.start_date.isoformat()
        if dag_run.end_date:
            details["finished_at"] = dag_run.end_date.isoformat()
    details["logical_date"] = str(context.get("logical_date") or "")
    return details


def on_dag_success(context):
    try:
        dag_run = context.get("dag_run")
        record_pipeline_run(
            context["dag"].dag_id,
            context["run_id"],
            "success",
            message="Ejecucion completada",
            details=_run_details(context),
        )
    except Exception:
        pass


def on_dag_failure(context):
    message = str(context.get("exception") or "Fallo sin detalle")[:500]
    try:
        record_pipeline_run(
            context["dag"].dag_id,
            context["run_id"],
            "failed",
            message=message,
            details=_run_details(context),
        )
    except Exception:
        pass
    if ALERT_WEBHOOK_URL:
        try:
            requests.post(
                ALERT_WEBHOOK_URL,
                json={
                    "dag_id": context["dag"].dag_id,
                    "run_id": context["run_id"],
                    "error": message,
                },
                timeout=5,
            )
        except requests.RequestException:
            pass
