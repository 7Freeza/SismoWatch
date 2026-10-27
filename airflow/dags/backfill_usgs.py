"""Carga historica parametrizada de los ultimos dias desde USGS sin duplicar."""

from datetime import datetime, timedelta, timezone

from airflow.decorators import dag, task
from airflow.operators.python import get_current_context

from include.alerts import on_dag_failure, on_dag_success
from include.datasets import RAW_EVENTS_DATASET
from include.db import persist_feed
from include.settings import QUERY_URL
from include.usgs import fetch_history

DEFAULT_ARGS = {
    "owner": "sismowatch",
    "retries": 2,
    "retry_delay": timedelta(seconds=45),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=25),
}


@dag(
    dag_id="backfill_usgs",
    description="Backfill manual de historico USGS por rango de dias",
    schedule=None,
    start_date=datetime(2026, 10, 1, tzinfo=timezone.utc),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["backfill", "usgs", "raw"],
    doc_md=__doc__,
    params={"days": 30, "minmagnitude": 2.5},
    on_success_callback=on_dag_success,
    on_failure_callback=on_dag_failure,
)
def backfill_usgs():
    @task(outlets=[RAW_EVENTS_DATASET])
    def load_history():
        context = get_current_context()
        conf = context["dag_run"].conf or {}
        days = max(1, min(int(conf.get("days", 30)), 60))
        min_magnitude = float(conf.get("minmagnitude", 2.5))
        end = datetime.now(timezone.utc)
        cursor = end - timedelta(days=days)
        total = 0
        requests_made = 0
        while cursor < end:
            chunk_end = min(cursor + timedelta(days=10), end)
            payload = fetch_history(cursor.date(), chunk_end.date(), min_magnitude)
            result = persist_feed(
                payload,
                f"{QUERY_URL}?starttime={cursor.date()}&endtime={chunk_end.date()}",
            )
            total += result["unique_events"]
            requests_made += 1
            cursor = chunk_end
        return {"days": days, "events": total, "requests": requests_made}

    load_history()


backfill_usgs()
