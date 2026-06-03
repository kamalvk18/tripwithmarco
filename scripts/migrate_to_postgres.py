"""
One-time migration: copy all data from SQLite → Postgres.

Usage:
    uv run scripts/migrate_to_postgres.py   # reads DATABASE_URL from .env
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ── Connect to SQLite source ───────────────────────────────────────────────────
sqlite_file = os.getenv("SQLITE_FILE", "data/trips.db")
if not os.path.exists(sqlite_file):
    print(f"SQLite file not found: {sqlite_file}")
    sys.exit(1)

pg_url = os.getenv("DATABASE_URL", "")
if not pg_url.startswith("postgresql"):
    print("Set DATABASE_URL=postgresql://... before running this script.")
    sys.exit(1)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sqlite_engine = create_engine(f"sqlite:///{sqlite_file}", connect_args={"check_same_thread": False})
pg_engine     = create_engine(pg_url)

SqliteSession = sessionmaker(bind=sqlite_engine)
PgSession     = sessionmaker(bind=pg_engine)

# ── Create tables in Postgres ──────────────────────────────────────────────────
# Import models so Base.metadata knows about them, then create all tables.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["DATABASE_URL"] = pg_url          # make database.py use Postgres
from backend.db.database import Base, init_db
init_db()
print("Postgres tables created (or already exist).")

# ── Migrate users ──────────────────────────────────────────────────────────────
with SqliteSession() as src, PgSession() as dst:
    try:
        users = src.execute(text("SELECT id, google_id, email, name, picture, created_at FROM users")).fetchall()
    except Exception:
        users = []

    if users:
        dst.execute(text("""
            INSERT INTO users (id, google_id, email, name, picture, created_at)
            VALUES (:id, :google_id, :email, :name, :picture, :created_at)
            ON CONFLICT (id) DO NOTHING
        """), [row._asdict() for row in users])
        dst.commit()
        print(f"Migrated {len(users)} users.")

        # Keep Postgres sequence in sync
        max_id = max(r.id for r in users)
        dst.execute(text(f"SELECT setval('users_id_seq', {max_id})"))
        dst.commit()
    else:
        print("No users to migrate.")

# ── Migrate trips ──────────────────────────────────────────────────────────────
with SqliteSession() as src, PgSession() as dst:
    trips = src.execute(text(
        "SELECT trip_id, user_id, destination, start_date, end_date, dates, saved_at, budget, currency, data FROM trips"
    )).fetchall()

    if trips:
        dst.execute(text("""
            INSERT INTO trips (trip_id, user_id, destination, start_date, end_date, dates, saved_at, budget, currency, data)
            VALUES (:trip_id, :user_id, :destination, :start_date, :end_date, :dates, :saved_at, :budget, :currency, :data)
            ON CONFLICT (trip_id) DO NOTHING
        """), [row._asdict() for row in trips])
        dst.commit()
        print(f"Migrated {len(trips)} trips.")
    else:
        print("No trips to migrate.")

# ── Migrate usage_logs ─────────────────────────────────────────────────────────
with SqliteSession() as src, PgSession() as dst:
    try:
        logs = src.execute(text(
            "SELECT id, user_id, endpoint, method, status_code, duration_ms, created_at FROM usage_logs"
        )).fetchall()
    except Exception:
        logs = []

    if logs:
        dst.execute(text("""
            INSERT INTO usage_logs (id, user_id, endpoint, method, status_code, duration_ms, created_at)
            VALUES (:id, :user_id, :endpoint, :method, :status_code, :duration_ms, :created_at)
            ON CONFLICT (id) DO NOTHING
        """), [row._asdict() for row in logs])
        dst.commit()

        max_id = max(r.id for r in logs)
        dst.execute(text(f"SELECT setval('usage_logs_id_seq', {max_id})"))
        dst.commit()
        print(f"Migrated {len(logs)} usage log entries.")
    else:
        print("No usage logs to migrate.")

print("Done.")
