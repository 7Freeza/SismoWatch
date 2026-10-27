"""Transforma raw a staging, aplica calidad y publica en curated."""

from datetime import datetime, timedelta, timezone

from airflow.decorators import dag, task
from airflow.exceptions import AirflowException
from airflow.operators.python import get_current_context

from include.alerts import on_dag_failure, on_dag_success
from include.datasets import RAW_EVENTS_DATASET
from include.db import (
    insert_quality_metrics,
    publish_curated,
    read_raw_events,
    upsert_staging,
)
from include.quality import build_metrics, evaluate

DEFAULT_ARGS = {
    "owner": "sismowatch",
    "retries": 2,
    "retry_delay": timedelta(seconds=30),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=3),
    "execution_timeout": timedelta(minutes=12),
}


@dag(
    dag_id="transform_quality",
    description="Limpia, valida y publica eventos sismicos en curated",
    schedule=[RAW_EVENTS_DATASET],
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["transformacion", "calidad", "staging", "curated"],
    doc_md=__doc__,
    on_success_callback=on_dag_success,
    on_failure_callback=on_dag_failure,
)
def transform_quality():
    @task
    def validate_and_stage():
        context = get_current_context()
        raw_records = read_raw_events()
        features = [record["payload"] for record in raw_records]
        valid, rejects = evaluate(features)
        upsert_staging(valid)
        metrics = build_metrics(len(features), len(valid), len(rejects), rejects)
        insert_quality_metrics(
            context["run_id"],
            metrics["total"],
            metrics["passed"],
            metrics["rejected"],
            metrics["score"],
            metrics["gate_passed"],
            metrics["rules"],
            metrics["details"],
        )
        if not metrics["gate_passed"]:
            raise AirflowException(
                f"Compuerta de calidad fallida: {metrics['score']} puntos, "
                f"{metrics['rejected']} rechazados de {metrics['total']}"
            )
        return {
            "total": metrics["total"],
            "passed": metrics["passed"],
            "rejected": metrics["rejected"],
            "score": metrics["score"],
        }

    @task
    def publish(counts):
        curated_rows = publish_curated()
        return {**counts, "curated_rows": curated_rows}

    publish(validate_and_stage())


transform_quality()
