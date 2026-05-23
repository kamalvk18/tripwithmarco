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
    POST /api/chat/stream                 → SSE streaming chat
    POST /api/chat                        → non-streaming chat
    GET  /docs                            → Swagger UI
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.api.routes.trips import router as trips_router
from backend.api.routes.chat import router as chat_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the email scheduler on startup; stop it on shutdown."""
    from backend.email.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Solo Travel Agent API",
    description="Marco — your AI travel companion.",
    version="0.2.0",
    lifespan=lifespan,
)

# Allow Streamlit (8501) and React dev server (5173)
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

app.include_router(trips_router, prefix="/api")
app.include_router(chat_router, prefix="/api")


@app.get("/health", tags=["meta"])
def health():
    """Liveness check — returns 200 when the server is up."""
    return {"status": "ok"}
