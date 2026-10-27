#!/usr/bin/env bash
set -euo pipefail

docker compose exec -T airflow-scheduler bash -lc \
  "cd /opt/airflow && PYTHONPATH=/opt/airflow:/opt/airflow/include pytest -q -p no:cacheprovider tests"
docker compose exec -T api bash -lc \
  "cd /app && pytest -q -p no:cacheprovider tests"
docker compose exec -T api bandit -r app -f txt
