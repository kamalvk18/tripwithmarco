"""
Admin-only analytics endpoints.

GET /api/admin/stats  → aggregated stats for users, trips, and API usage

Access is controlled by the ADMIN_EMAILS env var (comma-separated list).
"""

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func

from backend.auth.deps import get_admin_user
from backend.db.database import SessionLocal
from backend.db.models import Trip, User, UsageLog, ToolCallLog, ClaudeUsageLog

router = APIRouter(prefix="/admin", tags=["admin"])

# ── LLM pricing (USD per million tokens) ─────────────────────────────────────
# Input prices assume cache-miss (worst case). Add more models as needed.
_LLM_PRICING: dict[str, dict] = {
    "deepseek/deepseek-chat":              {"input": 0.27,  "output": 1.10},
    "deepseek/deepseek-reasoner":          {"input": 0.55,  "output": 2.19},
    "deepseek/deepseek-v4-pro":            {"input": 0.50,  "output": 1.50},
    "deepseek/deepseek-v4-flash":          {"input": 0.10,  "output": 0.40},
    "anthropic/claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00},
    "anthropic/claude-haiku-4-5-20251001": {"input": 0.25,  "output": 1.25},
    # Legacy names (before LiteLLM prefix was added)
    "claude-sonnet-4-6":                   {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5-20251001":           {"input": 0.25,  "output": 1.25},
}

_CHAT_ENDPOINTS = {"/api/chat/stream", "/api/chat", "/api/chat/extract"}
_SERPAPI_TOOLS  = {"search_flights", "search_hotels", "search_places"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    p = _LLM_PRICING.get(model, {"input": 0.0, "output": 0.0})
    return round((input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000, 4)


def _parse_saved_at(saved_at: str) -> datetime:
    try:
        dt = datetime.fromisoformat(saved_at)
        return _to_utc(dt)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


@router.get("/stats")
def get_stats(current_user: dict = Depends(get_admin_user)):
    now        = _utc_now()
    week_ago   = now - timedelta(days=7)
    month_ago  = now - timedelta(days=30)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    with SessionLocal() as session:

        # ── Users ─────────────────────────────────────────────────────────────
        all_users = session.query(User).order_by(User.created_at.desc()).all()
        total_users    = len(all_users)
        new_this_week  = sum(1 for u in all_users if u.created_at and _to_utc(u.created_at) >= week_ago)
        new_this_month = sum(1 for u in all_users if u.created_at and _to_utc(u.created_at) >= month_ago)

        # Last active = max UsageLog timestamp per user (all endpoints)
        last_active_rows = (
            session.query(UsageLog.user_id, func.max(UsageLog.created_at).label("last_active"))
            .group_by(UsageLog.user_id)
            .all()
        )
        last_active_map = {row.user_id: row.last_active for row in last_active_rows}

        recent_users = [
            {
                "id":             u.id,
                "name":           u.name,
                "email":          u.email,
                "created_at":     u.created_at.isoformat() if u.created_at else "",
                "last_active_at": last_active_map[u.id].isoformat() if u.id in last_active_map else "",
            }
            for u in all_users[:50]
        ]

        # ── Trips ─────────────────────────────────────────────────────────────
        all_trips = session.query(Trip).all()
        total_trips       = len(all_trips)
        created_this_week = sum(
            1 for t in all_trips
            if t.saved_at and _parse_saved_at(t.saved_at) >= week_ago
        )

        # Trips with an extracted itinerary (start_date set = extraction succeeded)
        completed_trips = sum(1 for t in all_trips if t.start_date and t.start_date.strip())
        completion_rate = round(completed_trips / total_trips * 100, 1) if total_trips else 0.0

        # Avg messages per trip (parse data blob; skip on failure)
        msg_counts = []
        for t in all_trips:
            try:
                data = json.loads(t.data)
                msgs = data.get("messages", [])
                if msgs:
                    msg_counts.append(len(msgs))
            except Exception:
                pass
        avg_messages_per_trip = round(sum(msg_counts) / len(msg_counts), 1) if msg_counts else None

        dest_counts = Counter(t.destination for t in all_trips if t.destination)
        top_destinations = [
            {"destination": dest, "count": cnt}
            for dest, cnt in dest_counts.most_common(10)
        ]
        budgets  = [t.budget for t in all_trips if t.budget is not None and t.budget > 0]
        avg_budget = round(sum(budgets) / len(budgets), 2) if budgets else None

        # ── Usage logs ────────────────────────────────────────────────────────
        all_logs = session.query(UsageLog).all()

        today_logs = [l for l in all_logs if l.created_at and _to_utc(l.created_at) >= today_start]
        week_logs  = [l for l in all_logs if l.created_at and _to_utc(l.created_at) >= week_ago]

        requests_today     = len(today_logs)
        requests_this_week = len(week_logs)
        errors_today       = sum(1 for l in today_logs if l.status_code and l.status_code >= 400)
        error_rate_today   = round(errors_today / requests_today * 100, 1) if requests_today else 0.0
        rate_limit_hits_today = sum(1 for l in today_logs if l.status_code == 429)

        # AI requests = chat endpoints only
        ai_today = [l for l in today_logs if l.endpoint in _CHAT_ENDPOINTS]
        ai_week  = [l for l in week_logs  if l.endpoint in _CHAT_ENDPOINTS]
        ai_requests_today = len(ai_today)
        ai_requests_week  = len(ai_week)

        # Active users = distinct users who made a chat request
        active_users_today = len({l.user_id for l in ai_today if l.user_id})
        active_users_week  = len({l.user_id for l in ai_week  if l.user_id})

        latencies   = [l.duration_ms for l in week_logs if l.duration_ms is not None]
        avg_latency_ms = round(sum(latencies) / len(latencies)) if latencies else None

        # Top 6 endpoints (last 7 days)
        endpoint_counts = Counter(l.endpoint for l in week_logs)
        top_endpoints = [
            {"endpoint": ep, "count": cnt}
            for ep, cnt in endpoint_counts.most_common(6)
        ]

        # Daily request counts — last 14 days
        daily: dict[str, dict] = {}
        for i in range(14):
            day = (now - timedelta(days=13 - i)).date()
            daily[day.isoformat()] = {"date": day.isoformat(), "requests": 0, "errors": 0, "ai_requests": 0}

        for log in all_logs:
            if not log.created_at:
                continue
            dt = _to_utc(log.created_at)
            if dt < now - timedelta(days=14):
                continue
            key = dt.date().isoformat()
            if key not in daily:
                continue
            daily[key]["requests"] += 1
            if log.status_code and log.status_code >= 400:
                daily[key]["errors"] += 1
            if log.endpoint in _CHAT_ENDPOINTS:
                daily[key]["ai_requests"] += 1

        daily_requests = list(daily.values())

        # ── Tool calls ────────────────────────────────────────────────────────
        all_tool_logs   = session.query(ToolCallLog).all()
        month_tool_logs = [l for l in all_tool_logs if l.created_at and _to_utc(l.created_at) >= month_ago]

        tool_stats: dict[str, dict] = {}
        for log in month_tool_logs:
            e = tool_stats.setdefault(log.tool_name, {"total": 0, "cache_hits": 0, "errors": 0, "latencies": []})
            e["total"] += 1
            if log.cache_hit:
                e["cache_hits"] += 1
            if not log.success:
                e["errors"] += 1
            if log.duration_ms is not None and not log.cache_hit:
                e["latencies"].append(log.duration_ms)

        serpapi_calls_this_month = sum(
            s["total"] - s["cache_hits"]
            for name, s in tool_stats.items()
            if name in _SERPAPI_TOOLS
        )

        tool_breakdown = [
            {
                "tool":          name,
                "total":         s["total"],
                "cache_hits":    s["cache_hits"],
                "errors":        s["errors"],
                "hit_rate":      round(s["cache_hits"] / s["total"] * 100, 1) if s["total"] else 0.0,
                "avg_latency_ms": round(sum(s["latencies"]) / len(s["latencies"])) if s["latencies"] else None,
            }
            for name, s in tool_stats.items()
        ]

        # ── LLM token usage ───────────────────────────────────────────────────
        all_llm_logs   = session.query(ClaudeUsageLog).all()
        month_llm_logs = [l for l in all_llm_logs if l.created_at and _to_utc(l.created_at) >= month_ago]

        llm_by_model: dict[str, dict] = {}
        for log in month_llm_logs:
            e = llm_by_model.setdefault(log.model, {
                "input_tokens": 0, "output_tokens": 0,
                "cache_read_tokens": 0, "cache_creation_tokens": 0, "calls": 0,
            })
            e["input_tokens"]          += log.input_tokens
            e["output_tokens"]         += log.output_tokens
            e["cache_read_tokens"]     += log.cache_read_tokens
            e["cache_creation_tokens"] += log.cache_creation_tokens
            e["calls"]                 += 1

        llm_models = [
            {
                "model": m,
                **v,
                "estimated_cost_usd": _estimate_cost(m, v["input_tokens"], v["output_tokens"]),
            }
            for m, v in llm_by_model.items()
        ]
        total_cost_usd = round(sum(m["estimated_cost_usd"] for m in llm_models), 4)

        # Daily tokens + cost — last 14 days
        daily_tokens: dict[str, dict] = {}
        for i in range(14):
            day = (now - timedelta(days=13 - i)).date().isoformat()
            daily_tokens[day] = {"date": day, "tokens": 0, "cost": 0.0, "model_breakdown": {}}

        for log in all_llm_logs:
            if not log.created_at:
                continue
            dt = _to_utc(log.created_at)
            if dt < now - timedelta(days=14):
                continue
            key = dt.date().isoformat()
            if key not in daily_tokens:
                continue
            tokens = (log.input_tokens or 0) + (log.output_tokens or 0)
            cost   = _estimate_cost(log.model, log.input_tokens or 0, log.output_tokens or 0)
            daily_tokens[key]["tokens"] += tokens
            daily_tokens[key]["cost"]    = round(daily_tokens[key]["cost"] + cost, 4)

        daily_llm = [
            {"date": d, "tokens": v["tokens"], "cost": v["cost"]}
            for d, v in daily_tokens.items()
        ]

    return {
        "users": {
            "total":              total_users,
            "new_this_week":      new_this_week,
            "new_this_month":     new_this_month,
            "active_today":       active_users_today,
            "active_this_week":   active_users_week,
            "recent":             recent_users,
        },
        "trips": {
            "total":                total_trips,
            "created_this_week":    created_this_week,
            "completed":            completed_trips,
            "completion_rate":      completion_rate,
            "avg_messages_per_trip": avg_messages_per_trip,
            "top_destinations":     top_destinations,
            "avg_budget":           avg_budget,
        },
        "usage": {
            "requests_today":       requests_today,
            "requests_this_week":   requests_this_week,
            "ai_requests_today":    ai_requests_today,
            "ai_requests_week":     ai_requests_week,
            "active_users_today":   active_users_today,
            "active_users_week":    active_users_week,
            "error_rate_today":     error_rate_today,
            "rate_limit_hits_today": rate_limit_hits_today,
            "avg_latency_ms":       avg_latency_ms,
            "top_endpoints":        top_endpoints,
            "daily_requests":       daily_requests,
        },
        "tools": {
            "serpapi_calls_this_month": serpapi_calls_this_month,
            "serpapi_monthly_cap":      250,
            "breakdown":                tool_breakdown,
        },
        "llm": {
            "models":          llm_models,
            "total_cost_usd":  total_cost_usd,
            "daily":           daily_llm,
        },
    }
