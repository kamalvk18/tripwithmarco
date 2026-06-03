import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# SQLite by default; swap to postgres via DATABASE_URL env var on Fly.io.
# For SQLite, DB_FILE controls the path so Fly.io volumes can use /data/trips.db.
DB_FILE = os.getenv("DB_FILE", "data/trips.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_FILE}")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create tables. Safe to call on every startup — no-op if tables exist."""
    if DATABASE_URL.startswith("sqlite"):
        os.makedirs(os.path.dirname(DB_FILE) or ".", exist_ok=True)
    from backend.db.models import User, Trip, UsageLog  # noqa: F401 — registers models
    Base.metadata.create_all(bind=engine)
