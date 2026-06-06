"""
Admin-only analytics endpoints.

GET /api/admin/stats  → aggregated stats for users, trips, and API usage

Access is controlled by the ADMIN_EMAILS env var (comma-separated list).
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func

from backend.auth.deps import get_admin_user
from backend.db.database import SessionLocal
from backend.db.models import Trip, User, UsageLog, ToolCallLog, ClaudeUsageLog

router = APIRouter(prefix="/admin", tags=["admin"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/stats")
def get_stats(current_user: dict = Depends(get_admin_user)):
    now = _utc_now()
    week_ago  = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    with SessionLocal() as session:
        # ── Users ─────────────────────────────────────────────────────────────
        all_users = session.query(User).order_by(User.created_at.desc()).all()
        total_users = len(all_users)
        new_this_week  = sum(1 for u in all_users if u.created_at and u.created_at.replace(tzinfo=timezone.utc) >= week_ago)
        new_this_month = sum(1 for u in all_users if u.created_at and u.created_at.replace(tzinfo=timezone.utc) >= month_ago)
        recent_users = [
            {"id": u.id, "name": u.name, "email": u.email, "created_at": u.created_at.isoformat() if u.created_at else ""}
            for u in all_users[:10]
        ]

        # ── Trips ─────────────────────────────────────────────────────────────
        all_trips = session.query(Trip).all()
        total_trips = len(all_trips)
        created_this_week = sum(
            1 for t in all_trips
            if t.saved_at and _parse_saved_at(t.saved_at) >= week_ago
        )
        dest_counts = Counter(t.destination for t in all_trips if t.destination)
        top_destinations = [
            {"destination": dest, "count": cnt}
            for dest, cnt in dest_counts.most_common(10)
        ]
        budgets = [t.budget for t in all_trips if t.budget is not None and t.budget > 0]
        avg_budget = round(sum(budgets) / len(budgets), 2) if budgets else None

        # ── Usage logs ────────────────────────────────────────────────────────
        all_logs = session.query(UsageLog).all()
        total_logs = len(all_logs)

        today_logs = [
            l for l in all_logs
            if l.created_at and l.created_at.replace(tzinfo=timezone.utc) >= today_start
        ]
        requests_today = len(today_logs)
        errors_today   = sum(1 for l in today_logs if l.status_code and l.status_code >= 400)
        error_rate_today = round(errors_today / requests_today * 100, 1) if requests_today else 0.0

        week_logs = [
            l for l in all_logs
            if l.created_at and l.created_at.replace(tzinfo=timezone.utc) >= week_ago
        ]
        requests_this_week = len(week_logs)

        latencies = [l.duration_ms for l in week_logs if l.duration_ms is not None]
        avg_latency_ms = round(sum(latencies) / len(latencies)) if latencies else None

        # Top 6 endpoints (by count) over last 7 days
        endpoint_counts = Counter(l.endpoint for l in week_logs)
        top_endpoints = [
            {"endpoint": ep, "count": cnt}
            for ep, cnt in endpoint_counts.most_common(6)
        ]

        # Daily request counts for last 14 days
        daily: dict[str, dict] = {}
        for i in range(14):
            day = (now - timedelta(days=13 - i)).date()
            daily[day.isoformat()] = {"date": day.isoformat(), "requests": 0, "errors": 0}

        for log in all_logs:
            if not log.created_at:
                continue
            dt = log.created_at.replace(tzinfo=timezone.utc)
            if dt < now - timedelta(days=14):
                continue
            key = dt.date().isoformat()
            if key in daily:
                daily[key]["requests"] += 1
                if log.status_code and log.status_code >= 400:
                    daily[key]["errors"] += 1

        daily_requests = list(daily.values())

        # ── Tool calls (SerpApi + OpenWeather) ────────────────────────────────
        _SERPAPI_TOOLS = {"search_flights", "search_hotels", "search_places"}

        all_tool_logs = session.query(ToolCallLog).all()
        month_tool_logs = [
            l for l in all_tool_logs
            if l.created_at and l.created_at.replace(tzinfo=timezone.utc) >= month_ago
        ]

        tool_stats: dict[str, dict] = {}
        for log in month_tool_logs:
            entry = tool_stats.setdefault(log.tool_name, {"total": 0, "cache_hits": 0, "errors": 0})
            entry["total"] += 1
            if log.cache_hit:
                entry["cache_hits"] += 1
            if not log.success:
                entry["errors"] += 1

        serpapi_calls_this_month = sum(
            s["total"] - s["cache_hits"]
            for name, s in tool_stats.items()
            if name in _SERPAPI_TOOLS
        )

        tool_breakdown = [
            {
                "tool": name,
                "total": s["total"],
                "cache_hits": s["cache_hits"],
                "errors": s["errors"],
                "hit_rate": round(s["cache_hits"] / s["total"] * 100, 1) if s["total"] else 0.0,
            }
            for name, s in tool_stats.items()
        ]

        # ── Claude token usage ────────────────────────────────────────────────
        all_claude_logs = session.query(ClaudeUsageLog).all()
        month_claude_logs = [
            l for l in all_claude_logs
            if l.created_at and l.created_at.replace(tzinfo=timezone.utc) >= month_ago
        ]

        claude_by_model: dict[str, dict] = {}
        for log in month_claude_logs:
            entry = claude_by_model.setdefault(log.model, {
                "input_tokens": 0, "output_tokens": 0,
                "cache_read_tokens": 0, "cache_creation_tokens": 0, "calls": 0,
            })
            entry["input_tokens"]          += log.input_tokens
            entry["output_tokens"]         += log.output_tokens
            entry["cache_read_tokens"]     += log.cache_read_tokens
            entry["cache_creation_tokens"] += log.cache_creation_tokens
            entry["calls"]                 += 1

        claude_models = [{"model": m, **v} for m, v in claude_by_model.items()]

        # Daily token totals for last 14 days (input + output combined)
        daily_tokens: dict[str, int] = {}
        for i in range(14):
            day = (now - timedelta(days=13 - i)).date().isoformat()
            daily_tokens[day] = 0
        for log in all_claude_logs:
            if not log.created_at:
                continue
            dt = log.created_at.replace(tzinfo=timezone.utc)
            if dt < now - timedelta(days=14):
                continue
            key = dt.date().isoformat()
            if key in daily_tokens:
                daily_tokens[key] += (log.input_tokens or 0) + (log.output_tokens or 0)
        daily_claude_tokens = [{"date": d, "tokens": t} for d, t in daily_tokens.items()]

    return {
        "users": {
            "total":          total_users,
            "new_this_week":  new_this_week,
            "new_this_month": new_this_month,
            "recent":         recent_users,
        },
        "trips": {
            "total":             total_trips,
            "created_this_week": created_this_week,
            "top_destinations":  top_destinations,
            "avg_budget":        avg_budget,
        },
        "usage": {
            "requests_today":      requests_today,
            "requests_this_week":  requests_this_week,
            "error_rate_today":    error_rate_today,
            "avg_latency_ms":      avg_latency_ms,
            "top_endpoints":       top_endpoints,
            "daily_requests":      daily_requests,
        },
        "tools": {
            "serpapi_calls_this_month": serpapi_calls_this_month,
            "serpapi_monthly_cap":      250,
            "breakdown":                tool_breakdown,
        },
        "claude": {
            "models":             claude_models,
            "daily_tokens":       daily_claude_tokens,
        },
    }


def _parse_saved_at(saved_at: str) -> datetime:
    """Parse saved_at string (ISO or timestamp format) to UTC datetime."""
    try:
        dt = datetime.fromisoformat(saved_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)
