import os
from pathlib import Path

INCLUDE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = INCLUDE_DIR / "prompts"

INGEST_DSN = os.getenv("DB_DSN_INGEST", "")
TRANSFORM_DSN = os.getenv("DB_DSN_TRANSFORM", "")
FEED_URL = os.getenv(
    "USGS_FEED_URL",
    "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson",
)
QUERY_URL = os.getenv(
    "USGS_QUERY_URL", "https://earthquake.usgs.gov/fdsnws/event/1/query"
)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
