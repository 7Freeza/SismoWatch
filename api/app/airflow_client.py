import requests
from fastapi import HTTPException

from app.config import settings


def trigger_dag(dag_id, conf):
    url = f"{settings.airflow_base_url}/api/v1/dags/{dag_id}/dagRuns"
    try:
        response = requests.post(
            url,
            auth=(settings.airflow_api_user, settings.airflow_api_password),
            json={"conf": conf},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Airflow no disponible") from exc
    if response.status_code not in (200, 201):
        raise HTTPException(
            status_code=502,
            detail=f"Airflow rechazo la ejecucion con estado {response.status_code}",
        )
    payload = response.json()
    return {
        "dag_id": dag_id,
        "dag_run_id": payload.get("dag_run_id"),
        "state": payload.get("state"),
    }
