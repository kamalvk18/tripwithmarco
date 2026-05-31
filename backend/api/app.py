"""
FastAPI application factory for Solo Travel Agent.

Start the API server:
    uvicorn backend.api.app:app --reload --port 8000

Or via main.py:
    uv run main.py --api

Endpoints:
    GET  /health                          → liveness check
    GET/POST/PUT/DELETE /api/trips[/{id}] → trip CRUD
    POST /api/trips/{id}/expenses         → log expense
    DELETE /api/trips/{id}/expenses/{id}  → remove expense
    POST /api/trips/{id}/checklist        → generate checklist
    PATCH /api/trips/{id}/checklist/{id}  → toggle checklist item
    POST /api/trips/{id}/email-config     → configure daily briefing
    POST /api/trips/{id}/send-briefing    → send briefing immediately (test)
    POST /api/send-briefings              → cron trigger: send all active briefings
    POST /api/chat/stream                 → SSE streaming chat
    POST /api/chat                        → non-streaming chat
    GET  /docs                            → Swagger UI
"""

import base64
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from dotenv import load_dotenv

from backend.api.routes.trips import router as trips_router
from backend.api.routes.chat import router as chat_router

load_dotenv()

# Path to the built React app (present in production Docker image; absent in dev)
_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


# ── Optional HTTP Basic Auth ──────────────────────────────────────────────────
# Set AUTH_USER and AUTH_PASS as Fly secrets to enable password protection.
# Leave them unset locally — the middleware skips auth entirely when absent.
class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth_user = os.getenv("AUTH_USER", "")
        auth_pass = os.getenv("AUTH_PASS", "")

        # Auth disabled — let everything through (local dev)
        if not auth_user or not auth_pass:
            return await call_next(request)

        # These paths must stay open (health checks + external cron trigger)
        if request.url.path in ("/health", "/api/send-briefings"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                username, _, password = decoded.partition(":")
                user_ok = secrets.compare_digest(username.encode(), auth_user.encode())
                pass_ok = secrets.compare_digest(password.encode(), auth_pass.encode())
                if user_ok and pass_ok:
                    return await call_next(request)
            except Exception:
                pass

        return Response(
            "Unauthorized — please log in.",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Solo Travel Agent"'},
        )


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
    version="0.2.0",
    lifespan=lifespan,
)

# ── Auth (added before CORS so it runs first) ─────────────────────────────────
app.add_middleware(BasicAuthMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────────
# In production the React app is served by FastAPI itself (same origin),
# so no cross-origin requests happen. Keep localhost entries for local dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(trips_router, prefix="/api")
app.include_router(chat_router, prefix="/api")


@app.get("/health", tags=["meta"])
def health():
    """Liveness check — returns 200 when the server is up."""
    return {"status": "ok"}


@app.post("/api/send-briefings", tags=["meta"])
def send_briefings(request: Request):
    """
    Trigger daily email briefings for all active trips.

    Called by an external cron service (e.g. cron-job.org) once per day.
    Protected by CRON_SECRET env var — pass it as X-Cron-Secret header.
    If CRON_SECRET is not set, the endpoint is open (safe for local dev).
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
# Vite outputs hashed asset files to dist/assets/ — mount them first so they're
# served efficiently. The catch-all below then returns index.html for every
# other path so React Router can handle client-side navigation.
if _DIST.is_dir():
    _assets = _DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="vite-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """Return index.html for all non-API paths (React Router SPA fallback)."""
        return FileResponse(str(_DIST / "index.html"))
