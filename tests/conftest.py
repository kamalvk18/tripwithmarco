"""
Test environment isolation — runs before any test module imports backend code.

The real .env may point DATABASE_URL at production (Neon). Tests must never
touch it: we pin a throwaway SQLite file here, BEFORE backend.db.database
creates its engine at import time. app.py's load_dotenv() does not override
existing env vars, so these values win.
"""

import os
import tempfile

_TEST_DB_DIR = tempfile.mkdtemp(prefix="marco-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_DIR}/test_trips.db"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

# Create tables now — TestClient is used without lifespan, so init_db()
# would otherwise never run and rate-limit queries would 500.
from backend.db.database import init_db  # noqa: E402  (import after env pin is the point)

init_db()
