import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault(
    "DB_DSN_READER",
    "postgresql+psycopg2://api_reader:test@postgres:5432/sismowatch",
)
os.environ.setdefault("JWT_SECRET", "test_secret")
os.environ.setdefault("AI_ENABLED", "false")
