from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

reader_engine = create_engine(
    settings.db_dsn_reader, pool_pre_ping=True, pool_size=5, max_overflow=5
)
ReaderSession = sessionmaker(bind=reader_engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = ReaderSession()
    try:
        yield db
    finally:
        db.close()
