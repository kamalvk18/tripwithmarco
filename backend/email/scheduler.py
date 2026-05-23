"""
APScheduler job that fires send_all_active_briefings() every morning.

The send time is configurable per-trip via trip_data["email_config"]["send_time"]
(HH:MM, 24h). The scheduler fires once per minute and delegates to each trip's
configured time — this avoids needing one job per trip.

Started automatically when FastAPI starts (via lifespan in backend/api/app.py).
"""

import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

_scheduler: BackgroundScheduler | None = None


def _run_briefings() -> None:
    """Check all active trips and send briefings if it's their configured time."""
    from backend.db.trip_store import list_trips, load_trip
    from backend.email.briefing import send_briefing

    now_hhmm = datetime.now().strftime("%H:%M")
    for summary in list_trips():
        trip = load_trip(summary["trip_id"])
        if not trip:
            continue
        cfg = trip.get("email_config") or {}
        if not cfg.get("enabled"):
            continue
        send_time = cfg.get("send_time", "07:00")
        if send_time != now_hhmm:
            continue
        to_email = cfg.get("email", "")
        if to_email:
            send_briefing(summary["trip_id"], to_email)


def start_scheduler() -> None:
    """Start the background scheduler. Call once on app startup."""
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(_run_briefings, "cron", minute="*")   # fire every minute
    _scheduler.start()
    print("⏰  Email scheduler started (checks trips every minute)")


def stop_scheduler() -> None:
    """Gracefully stop the scheduler on app shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("⏰  Email scheduler stopped")
