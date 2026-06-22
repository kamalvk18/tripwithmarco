"""
Per-user daily rate limiting backed by the UsageLog table.

Limits are read from env vars at request time so they can be changed
without redeploying:
    DAILY_TRIP_LIMIT   — max POST /api/trips per user per UTC day  (default 2)
    DAILY_CHAT_LIMIT   — max chat requests per user per UTC day    (default 20)
"""

import os
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from sqlalchemy import func

from backend.auth.deps import get_current_user
from backend.db.database import SessionLocal
from backend.db.models import UsageLog

def _today_start_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)


def _count_today(user_id: int, endpoint: str, method: str = "POST") -> int:
    with SessionLocal() as session:
        return session.query(func.count(UsageLog.id)).filter(
            UsageLog.user_id == user_id,
            UsageLog.endpoint == endpoint,
            UsageLog.method == method,
            UsageLog.status_code < 400,
            UsageLog.created_at >= _today_start_utc(),
        ).scalar() or 0


def _count_today_prefix(user_id: int, prefix: str, method: str = "POST") -> int:
    """Count requests today where endpoint starts with the given prefix."""
    with SessionLocal() as session:
        return session.query(func.count(UsageLog.id)).filter(
            UsageLog.user_id == user_id,
            UsageLog.endpoint.like(f"{prefix}%"),
            UsageLog.method == method,
            UsageLog.status_code < 400,
            UsageLog.created_at >= _today_start_utc(),
        ).scalar() or 0


def _ai_request_count(user_id: int) -> int:
    """Total AI-backed requests today across all Claude-consuming endpoints."""
    return (
        _count_today(user_id, "/api/chat/stream")
        + _count_today(user_id, "/api/chat")
        + _count_today(user_id, "/api/chat/extract")
        + _count_today_prefix(user_id, "/api/trips/", method="POST")  # checklist
        + _count_today_prefix(user_id, "/api/trips/", method="PATCH")  # debrief, etc.
    )


def check_trip_limit(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("is_admin"):
        return current_user
    limit = int(os.getenv("DAILY_TRIP_LIMIT", "2"))
    count = _count_today(current_user["id"], "/api/trips")
    if count >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily trip limit reached ({limit} trips/day). Try again tomorrow.",
        )
    return current_user


def check_chat_limit(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("is_admin"):
        return current_user
    limit = int(os.getenv("DAILY_CHAT_LIMIT", "20"))
    count = (
        _count_today(current_user["id"], "/api/chat/stream")
        + _count_today(current_user["id"], "/api/chat")
        + _count_today(current_user["id"], "/api/chat/extract")
    )
    if count >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily chat limit reached ({limit} messages/day). Try again tomorrow.",
        )
    return current_user


def check_claude_limit(current_user: dict = Depends(get_current_user)) -> dict:
    """Shared daily budget for all Claude-backed endpoints (chat, checklist, debrief, extract)."""
    if current_user.get("is_admin"):
        return current_user
    limit = int(os.getenv("DAILY_CHAT_LIMIT", "20"))
    count = _ai_request_count(current_user["id"])
    if count >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit reached ({limit} AI requests/day). Try again tomorrow.",
        )
    return current_user
