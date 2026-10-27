import requests
from airflow.exceptions import AirflowException

from include.settings import FEED_URL, QUERY_URL

HEADERS = {"User-Agent": "SismoWatch/1.0"}


def fetch_json(url, params=None, timeout=30):
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        raise AirflowException(f"USGS no disponible: {exc}") from exc
    if response.status_code != 200:
        raise AirflowException(f"USGS respondio con estado {response.status_code}")
    content_type = response.headers.get("Content-Type", "")
    if "json" not in content_type.lower():
        raise AirflowException("USGS devolvio un contenido que no es JSON")
    try:
        payload = response.json()
    except ValueError as exc:
        raise AirflowException("USGS devolvio JSON invalido") from exc
    if payload.get("type") != "FeatureCollection":
        raise AirflowException("USGS devolvio un GeoJSON inesperado")
    if not isinstance(payload.get("features"), list):
        raise AirflowException("USGS no incluyo la lista de features")
    return payload


def fetch_feed():
    return fetch_json(FEED_URL, timeout=30)


def fetch_history(start, end, min_magnitude=2.5):
    params = {
        "format": "geojson",
        "starttime": start.isoformat(),
        "endtime": end.isoformat(),
        "minmagnitude": min_magnitude,
        "orderby": "time-asc",
    }
    return fetch_json(QUERY_URL, params=params, timeout=90)
