"""
Google OAuth 2.0 authentication routes.

GET  /api/auth/google/login    → redirect to Google consent screen
GET  /api/auth/google/callback → exchange code, issue JWT, redirect to frontend
GET  /api/auth/me              → return current user (requires Bearer token)

Required env vars:
    GOOGLE_CLIENT_ID
    GOOGLE_CLIENT_SECRET
    JWT_SECRET         (defaults to dev placeholder — set in production)
    FRONTEND_URL       (defaults to http://localhost:5173)
"""

import os
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from starlette.requests import Request

from backend.auth.deps import get_current_user
from backend.auth.jwt_utils import create_token
from backend.db.database import SessionLocal
from backend.db.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
FRONTEND_URL         = os.getenv("FRONTEND_URL", "http://localhost:5173")

# In-memory CSRF state store — acceptable for single-server; use Redis for scale
_pending_states: dict[str, float] = {}
_STATE_TTL = 600  # seconds


def _callback_uri(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api/auth/google/callback"


@router.get("/google/login")
async def google_login(request: Request):
    """Redirect the browser to Google's OAuth consent screen."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google OAuth is not configured on this server")

    state = secrets.token_urlsafe(32)
    now   = time.time()
    _pending_states[state] = now

    # Clean up expired states
    expired = [k for k, v in list(_pending_states.items()) if now - v > _STATE_TTL]
    for k in expired:
        _pending_states.pop(k, None)

    params = {
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  _callback_uri(request),
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "offline",
        "prompt":        "select_account",
    }
    return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))


@router.get("/google/callback")
async def google_callback(code: str, state: str, request: Request):
    """Exchange the OAuth code for a JWT and redirect to the frontend."""
    if state not in _pending_states:
        raise HTTPException(400, "Invalid OAuth state — please try signing in again")
    del _pending_states[state]

    redirect_uri = _callback_uri(request)

    # Exchange code → access token
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code":          code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  redirect_uri,
                "grant_type":    "authorization_code",
            },
        )
    if token_res.status_code != 200:
        raise HTTPException(400, "Google token exchange failed")
    access_token = token_res.json().get("access_token")

    # Fetch Google profile
    async with httpx.AsyncClient() as client:
        profile_res = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if profile_res.status_code != 200:
        raise HTTPException(400, "Failed to fetch Google profile")

    g = profile_res.json()
    google_id = g["sub"]
    email     = g.get("email", "")
    name      = g.get("name", "")
    picture   = g.get("picture", "")

    # Upsert user in DB
    with SessionLocal() as session:
        user = session.query(User).filter_by(google_id=google_id).first()
        if user is None:
            user = User(google_id=google_id, email=email, name=name, picture=picture)
            session.add(user)
        else:
            user.email   = email
            user.name    = name
            user.picture = picture
        session.commit()
        session.refresh(user)
        user_id = user.id

    jwt = create_token(user_id, email, name, picture)
    # Fragment (#) never reaches the server or appears in access logs, preventing
    # the JWT from leaking into Render/Nginx logs or browser history via query params.
    return RedirectResponse(f"{FRONTEND_URL}/auth/callback#{jwt}")


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user
