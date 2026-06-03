"""
FastAPI application factory for Solo Travel Agent.

Start the API server:
    uvicorn backend.api.app:app --reload --port 8000

Or via main.py:
    uv run main.py --api

Endpoints:
    GET  /health                          → liveness check
    GET  /api/auth/google/login           → start Google OAuth flow
    GET  /api/auth/google/callback        → OAuth callback, issues JWT
    GET  /api/auth/me                     → current user profile
    GET/POST/PUT/DELETE /api/trips[/{id}] → trip CRUD (auth required)
    POST /api/trips/{id}/expenses         → log expense
    DELETE /api/trips/{id}/expenses/{id}  → remove expense
    POST /api/trips/{id}/checklist        → generate checklist
    PATCH /api/trips/{id}/checklist/{id}  → toggle checklist item
    POST /api/trips/{id}/email-config     → configure daily briefing
    POST /api/trips/{id}/send-briefing    → send briefing immediately (test)
    POST /api/send-briefings              → cron trigger: send all active briefings
    POST /api/chat/stream                 → SSE streaming chat (auth required)
    GET  /docs                            → Swagger UI
"""

import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from dotenv import load_dotenv

from backend.api.routes.trips import router as trips_router
from backend.api.routes.chat import router as chat_router
from backend.api.routes.auth import router as auth_router

load_dotenv()

_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


# ── Usage logging middleware ───────────────────────────────────────────────────
# Logs every /api/ request to the usage_logs table.
# Non-blocking: the DB write runs in a thread-pool executor so it never delays
# the HTTP response, even if SQLite has a brief lock.

def _write_usage_log(user_id, endpoint, method, status_code, duration_ms):
    try:
        from backend.db.database import SessionLocal
        from backend.db.models import UsageLog
        with SessionLocal() as session:
            session.add(UsageLog(
                user_id=user_id,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
            ))
            session.commit()
    except Exception:
        pass


def _extract_user_id(request: Request) -> int | None:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        from backend.auth.jwt_utils import verify_token
        payload = verify_token(auth[7:])
        return int(payload["sub"])
    except Exception:
        return None


class UsageLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        import asyncio
        start    = time.monotonic()
        response = await call_next(request)
        duration = int((time.monotonic() - start) * 1000)

        path = request.url.path
        if path.startswith("/api/") and path not in ("/api/send-briefings",):
            user_id = _extract_user_id(request)
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                _write_usage_log,
                user_id, path, request.method, response.status_code, duration,
            )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.db.database import init_db
    from backend.db.trip_store import migrate_from_json, seed_demo_trips
    init_db()
    migrate_from_json()
    seed_demo_trips()
    yield


app = FastAPI(
    title="Solo Travel Agent API",
    description="Marco — your AI travel companion.",
    version="0.3.0",
    lifespan=lifespan,
)

# ── Middleware (order matters: outermost added last runs first) ────────────────
app.add_middleware(UsageLogMiddleware)

_cors_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
]
# ALLOWED_ORIGINS is a comma-separated list of extra origins (e.g. Vercel URL)
for _o in os.getenv("ALLOWED_ORIGINS", "").split(","):
    if _o.strip():
        _cors_origins.append(_o.strip())

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(auth_router,  prefix="/api")
app.include_router(trips_router, prefix="/api")
app.include_router(chat_router,  prefix="/api")


@app.get("/health", tags=["meta"])
def health():
    """Liveness check — returns 200 when the server is up."""
    return {"status": "ok"}


@app.post("/api/send-briefings", tags=["meta"])
def send_briefings(request: Request):
    """
    Trigger daily email briefings for all active trips.

    Called by an external cron service once per day.
    Protected by CRON_SECRET env var — pass it as X-Cron-Secret header.
    """
    cron_secret = os.getenv("CRON_SECRET", "")
    if cron_secret:
        provided = request.headers.get("X-Cron-Secret", "")
        if not secrets.compare_digest(provided.encode(), cron_secret.encode()):
            raise HTTPException(status_code=403, detail="Invalid or missing X-Cron-Secret")

    from backend.email.briefing import send_all_active_briefings
    sent = send_all_active_briefings()
    return {"ok": True, "sent": sent}


# ── React SPA static files (production only) ──────────────────────────────────
if _DIST.is_dir():
    _assets = _DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="vite-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(str(_DIST / "index.html"))
