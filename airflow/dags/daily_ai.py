"""Detecta anomalias sismicas y genera el reporte ejecutivo diario con IA."""

from datetime import datetime, timedelta, timezone

from airflow.decorators import dag, task

from include.ai import detect_anomalies, generate_report
from include.alerts import on_dag_failure, on_dag_success
from include.db import connection
from include.settings import TRANSFORM_DSN

DEFAULT_ARGS = {
    "owner": "sismowatch",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "execution_timeout": timedelta(minutes=15),
}


@dag(
    dag_id="daily_ai",
    description="Genera alertas de anomalias y reporte narrativo diario",
    schedule="0 6 * * *",
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["ia", "anomalias", "reporte"],
    doc_md=__doc__,
    on_success_callback=on_dag_success,
    on_failure_callback=on_dag_failure,
)
def daily_ai():
    @task
    def find_anomalies():
        with connection(TRANSFORM_DSN) as conn:
            return {"anomalies": detect_anomalies(conn)}

    @task
    def write_report():
        with connection(TRANSFORM_DSN) as conn:
            return generate_report(conn)

    find_anomalies() >> write_report()


daily_ai()
