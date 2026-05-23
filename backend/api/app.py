"""
FastAPI application factory for Solo Travel Agent.

Start the API server:
    uvicorn backend.api.app:app --reload --port 8000

Or via main.py:
    uv run main.py --api

Endpoints:
    GET  /health           → liveness check
    GET  /trips            → list saved trips
    GET  /trips/{id}       → trip detail
    POST /trips            → save a new trip
    PUT  /trips/{id}       → update existing trip
    DELETE /trips/{id}     → delete trip
    POST /chat/stream      → SSE streaming chat
    POST /chat             → non-streaming chat (returns full JSON)
    GET  /docs             → Swagger UI (auto-generated)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.api.routes.trips import router as trips_router
from backend.api.routes.chat import router as chat_router

load_dotenv()

app = FastAPI(
    title="Solo Travel Agent API",
    description="Marco — your AI travel companion.",
    version="0.1.0",
)

# Allow Streamlit (localhost:8501) and any local dev client to reach the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000", "http://localhost:5173"],
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
