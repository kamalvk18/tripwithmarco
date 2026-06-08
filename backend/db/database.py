import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# SQLite by default; swap to Postgres via DATABASE_URL env var (e.g. Neon connection string).
# DB_FILE controls the SQLite path; set to /data/trips.db when using a persistent volume.
DB_FILE = os.getenv("DB_FILE", "data/trips.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_FILE}")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def _apply_migrations() -> None:
    """Additive schema migrations — safe to re-run on every startup."""
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE trips ADD COLUMN invite_token TEXT"))
            conn.commit()
        except Exception:
            pass  # Column already exists (SQLite raises on duplicate ALTER)


def init_db() -> None:
    """Create tables. Safe to call on every startup — no-op if tables exist."""
    if DATABASE_URL.startswith("sqlite"):
        os.makedirs(os.path.dirname(DB_FILE) or ".", exist_ok=True)
    from backend.db.models import User, Trip, TripMember, UsageLog, ToolCallLog, ClaudeUsageLog  # noqa: F401 — registers models
    Base.metadata.create_all(bind=engine)
    _apply_migrations()
