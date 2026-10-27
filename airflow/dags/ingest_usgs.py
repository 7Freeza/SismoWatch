"""Ingesta cada cinco minutos del feed publico de sismos de USGS hacia raw."""

from datetime import datetime, timedelta, timezone

from airflow.decorators import dag, task
from airflow.exceptions import AirflowException

from include.alerts import on_dag_failure, on_dag_success
from include.datasets import RAW_EVENTS_DATASET
from include.db import persist_feed
from include.settings import FEED_URL
from include.usgs import fetch_feed

DEFAULT_ARGS = {
    "owner": "sismowatch",
    "retries": 3,
    "retry_delay": timedelta(seconds=30),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=8),
}


@dag(
    dag_id="ingest_usgs",
    description="Descarga el feed all_hour de USGS y lo guarda en raw",
    schedule="*/5 * * * *",
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["ingesta", "usgs", "raw"],
    doc_md=__doc__,
    on_success_callback=on_dag_success,
    on_failure_callback=on_dag_failure,
)
def ingest_usgs():
    @task(outlets=[RAW_EVENTS_DATASET])
    def ingest_feed():
        payload = fetch_feed()
        result = persist_feed(payload, FEED_URL)
        if result["features"] == 0:
            raise AirflowException("USGS no devolvio eventos en esta ejecucion")
        return result

    ingest_feed()


ingest_usgs()
