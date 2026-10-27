from airflow.models import DagBag
from airflow.timetables.simple import DatasetTriggeredTimetable


def test_all_dags_import_without_errors():
    bag = DagBag(dag_folder="/opt/airflow/dags", include_examples=False)
    assert bag.import_errors == {}
    assert {"ingest_usgs", "transform_quality", "backfill_usgs", "daily_ai"}.issubset(
        set(bag.dag_ids)
    )


def test_transform_quality_is_dataset_triggered():
    bag = DagBag(dag_folder="/opt/airflow/dags", include_examples=False)
    dag = bag.get_dag("transform_quality")
    assert isinstance(dag.timetable, DatasetTriggeredTimetable)
