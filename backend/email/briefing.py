"""
Daily trip briefing email.

Generates an HTML email for an active trip day using companion-mode logic
(weather + today's plan) and sends it via Resend.

Required env var:
    RESEND_API_KEY — get a free key at resend.com (3,000 emails/month free)

Optional env var:
    RESEND_FROM — sender address (default: Marco <marco@marco.app>)
                  Must be a verified domain in your Resend account.
                  For testing, Resend's sandbox allows any address.
"""

import os
import re
import textwrap
from datetime import date, datetime

import resend
from dotenv import load_dotenv

from backend.tools.weather import get_weather_forecast
from backend.db.trip_store import load_trip, list_trips

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY", "")
_FROM = os.getenv("RESEND_FROM", "Marco <marco@marco.app>")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_day_section(itinerary: str, day_number: int) -> str:
    """Pull a single day's text from the itinerary."""
    pattern = re.compile(
        rf'(?i)((?:#{1,3}\s*)?\*{{0,2}}DAY\s+{day_number}\b.*?)(?=(?:#{1,3}\s*)?\*{{0,2}}DAY\s+\d+|\Z)',
        re.DOTALL,
    )
    m = pattern.search(itinerary)
    return m.group(1).strip() if m else ""


def _spent_total(spending: list[dict]) -> float:
    return sum(e.get("amount", 0) for e in spending)


def _esc(text: str) -> str:
    """HTML-escape user-supplied text before embedding in email HTML."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
    )


def _md_to_html(md: str) -> str:
    """Minimal Markdown → HTML (bold, italic, bullets). No external deps."""
    lines = []
    in_ul = False
    for line in md.splitlines():
        stripped = line.strip()
        # Headings — escape content but keep the heading tag
        if stripped.startswith("### "):
            if in_ul: lines.append("</ul>"); in_ul = False
            lines.append(f"<h3>{_esc(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            if in_ul: lines.append("</ul>"); in_ul = False
            lines.append(f"<h2>{_esc(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            if in_ul: lines.append("</ul>"); in_ul = False
            lines.append(f"<h1>{_esc(stripped[2:])}</h1>")
        # Bullets
        elif stripped.startswith(("- ", "* ", "• ")):
            if not in_ul: lines.append("<ul>"); in_ul = True
            content = _esc(stripped[2:])
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
            content = re.sub(r'\*(.+?)\*',     r'<em>\1</em>',          content)
            lines.append(f"<li>{content}</li>")
        elif stripped == "":
            if in_ul: lines.append("</ul>"); in_ul = False
            lines.append("<br>")
        else:
            if in_ul: lines.append("</ul>"); in_ul = False
            text = _esc(stripped)
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            text = re.sub(r'\*(.+?)\*',     r'<em>\1</em>',          text)
            lines.append(f"<p>{text}</p>")
    if in_ul:
        lines.append("</ul>")
    return "\n".join(lines)


def _build_html(
    destination: str,
    day_number: int,
    total_days: int,
    weather_text: str,
    today_plan_html: str,
    currency: str,
    budget: float,
    spent: float,
    budget_breakdown: dict,
) -> str:
    remaining = budget - spent if budget else 0
    spent_str     = f"{currency} {spent:,.0f}"
    budget_str    = f"{currency} {budget:,.0f}" if budget else "—"
    remaining_str = f"{currency} {remaining:,.0f}" if budget else "—"
    over = budget > 0 and spent > budget

    weather_html = _md_to_html(weather_text) if weather_text else "<p>Weather data unavailable.</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Marco's Briefing — Day {day_number}</title>
<style>
  body {{font-family:system-ui,sans-serif;background:#f8f9fa;margin:0;padding:0;color:#1e293b}}
  .wrap {{max-width:600px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)}}
  .header {{background:#4f46e5;color:#fff;padding:28px 32px}}
  .header h1 {{margin:0 0 4px;font-size:22px;font-weight:700}}
  .header p  {{margin:0;opacity:.8;font-size:14px}}
  .section {{padding:24px 32px;border-bottom:1px solid #e2e8f0}}
  .section:last-child {{border-bottom:none}}
  .label {{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:#94a3b8;margin-bottom:8px}}
  h2 {{font-size:16px;margin:0 0 12px;color:#0f172a}}
  h3 {{font-size:14px;margin:12px 0 6px;color:#1e293b}}
  p  {{margin:6px 0;font-size:14px;line-height:1.6;color:#475569}}
  ul {{margin:6px 0 6px 18px;padding:0}} li {{font-size:14px;line-height:1.6;color:#475569;margin:2px 0}}
  strong {{color:#1e293b}}
  .budget-row {{display:flex;justify-content:space-between;font-size:14px;padding:4px 0}}
  .budget-row span:first-child {{color:#64748b}}
  .budget-row span:last-child  {{font-weight:600;color:#1e293b}}
  .over {{color:#ef4444!important}}
  .footer {{background:#f1f5f9;padding:16px 32px;text-align:center;font-size:12px;color:#94a3b8}}
  br {{display:block;margin:4px 0}}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>☀️ Good morning — Day {day_number} of {total_days}</h1>
    <p>{_esc(destination)} · {date.today().strftime("%A, %B %-d")}</p>
  </div>

  <div class="section">
    <div class="label">🌤 Today's Weather</div>
    {weather_html}
  </div>

  <div class="section">
    <div class="label">📍 Today's Plan</div>
    {today_plan_html}
  </div>

  <div class="section">
    <div class="label">💰 Budget</div>
    <div class="budget-row"><span>Spent so far</span><span class="{'over' if over else ''}">{spent_str}</span></div>
    <div class="budget-row"><span>Total budget</span><span>{budget_str}</span></div>
    <div class="budget-row"><span>Remaining</span><span class="{'over' if over else ''}">{remaining_str}</span></div>
    {'<p style="color:#ef4444;font-size:13px;margin-top:8px">⚠️ You\'re over budget. Consider cheaper options today.</p>' if over else ''}
  </div>

  <div class="footer">
    Sent by Marco<br>
    <a href="#" style="color:#6366f1">Manage email preferences</a>
  </div>
</div>
</body>
</html>"""


# ── Public API ────────────────────────────────────────────────────────────────

def send_briefing(trip_id: str, to_email: str) -> bool:
    """
    Generate and send today's briefing for an active trip.

    Returns True if the email was sent, False otherwise (wrong day, missing key, etc.).
    """
    if not resend.api_key:
        print("⚠️  RESEND_API_KEY not set — skipping email send")
        return False

    trip = load_trip(trip_id)
    if not trip:
        return False

    # Only send on active trip days
    today = date.today()
    try:
        start = date.fromisoformat(trip["start_date"])
        end   = date.fromisoformat(trip["end_date"])
    except (KeyError, ValueError):
        return False

    if not (start <= today <= end):
        return False

    day_number = (today - start).days + 1
    total_days = (end - start).days + 1

    # Extract today's plan — use the LAST assistant message that has day content,
    # not the first (which is often Marco's options/clarifying questions).
    messages        = trip.get("messages", [])
    assistant_msgs  = [m["content"] for m in messages if m["role"] == "assistant"]
    itinerary       = next(
        (c for c in reversed(assistant_msgs) if re.search(r'\bday\s+\d+\b', c, re.IGNORECASE)),
        assistant_msgs[0] if assistant_msgs else "",
    )
    day_plan = _extract_day_section(itinerary, day_number)
    if not day_plan:
        day_plan = "No specific plan found for today."

    # Live weather — only today's forecast, not the full 5-day dump
    city = trip.get("city") or trip.get("destination", "")
    weather_text = ""
    try:
        weather_raw   = get_weather_forecast(city)
        today_str     = today.isoformat()
        today_weather = next(
            (d for d in weather_raw.get("forecast", []) if d["date"] == today_str),
            None,
        )
        if today_weather:
            rain = " ☔ Rain expected" if today_weather["rain_expected"] else ""
            weather_text = (
                f"**{today_weather['condition']}**{rain}  \n"
                f"🌡 {today_weather['min_temp']}°C – {today_weather['max_temp']}°C "
                f"(avg {today_weather['avg_temp']}°C)"
            )
        elif "error" not in weather_raw:
            weather_text = "Weather data not available for today."
    except Exception:
        weather_text = ""

    # Budget summary
    currency  = trip.get("currency", "EUR")
    budget    = float(trip.get("budget") or 0)
    spending  = trip.get("spending") or []
    spent     = _spent_total(spending)
    breakdown = trip.get("budget_breakdown") or {}

    html = _build_html(
        destination   = trip.get("destination", ""),
        day_number    = day_number,
        total_days    = total_days,
        weather_text  = weather_text,
        today_plan_html = _md_to_html(day_plan),
        currency      = currency,
        budget        = budget,
        spent         = spent,
        budget_breakdown = breakdown,
    )

    destination = trip.get("destination", "Your Trip")
    try:
        resend.Emails.send({
            "from":    _FROM,
            "to":      [to_email],
            "subject": f"☀️ Marco's Day {day_number} Briefing — {destination}",
            "html":    html,
        })
        print(f"✉️  Briefing sent to {to_email} for {destination} Day {day_number}")
        return True
    except Exception as exc:
        print(f"❌  Email send failed: {exc}")
        return False


def send_all_active_briefings() -> int:
    """
    Called by the scheduler each morning.
    Finds all active trips with email configured and sends briefings.
    Returns count of emails sent.
    """
    sent = 0
    for summary in list_trips():
        trip = load_trip(summary["trip_id"])
        if not trip:
            continue
        cfg = trip.get("email_config") or {}
        if not cfg.get("enabled"):
            continue
        to_email = cfg.get("email", "")
        if not to_email:
            continue
        if send_briefing(summary["trip_id"], to_email):
            sent += 1
    return sent
