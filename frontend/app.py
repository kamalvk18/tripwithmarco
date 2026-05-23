import re
import streamlit as st
import sys
import os
from datetime import date, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import frontend.api_client as api
# Pure parsing helpers — no I/O, safe to import directly
from backend.agents.planning_agent import extract_itinerary, extract_all_days

# Convenience aliases that match the old call-site names
list_trips   = api.list_trips
load_trip    = api.load_trip
save_trip    = api.save_trip
update_trip  = api.update_trip
delete_trip  = api.delete_trip

# ── Tool-call display helpers ─────────────────────────────────────────────────
_TOOL_LABELS = {
    "search_flights":  "✈️ Checking flights...",
    "search_hotels":   "🏨 Searching hotels...",
    "search_places":   "📍 Finding local spots...",
    "get_weather":     "🌤️ Fetching weather...",
}

def _make_tool_status_callback(status_el):
    """Return an on_tool_call callback that updates a Streamlit empty element."""
    def _callback(tool_name: str, _tool_input: dict):
        label = _TOOL_LABELS.get(tool_name, f"🔧 Running {tool_name}...")
        status_el.caption(label)
    return _callback

# ── Page config ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Trip Companion",
    page_icon="✈️",
    layout="wide"
)

# ── Helpers ───────────────────────────────────────────────────────────────────────
def get_trip_status(trip: dict):
    """Returns (status, extra) where extra is day_number if active, days_until if upcoming."""
    try:
        s = date.fromisoformat(trip.get("start_date", ""))
        e = date.fromisoformat(trip.get("end_date", ""))
        today = date.today()
        if today < s:
            return "upcoming", (s - today).days
        elif s <= today <= e:
            return "active", (today - s).days + 1
        else:
            return "past", None
    except Exception:
        return "unknown", None

def clear_plan_state():
    for key in ["active_trip_id", "trip_data", "companion_mode",
                "itinerary_generated", "save_destination", "save_city",
                "save_country", "save_start", "save_end"]:
        st.session_state.pop(key, None)
    st.session_state.messages = []

# ── Sidebar ───────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ✈️ Trip Companion")
    st.caption("Your AI-powered travel planner")

    if not api.is_api_running():
        st.error(
            "⚠️ **API server offline**\n\n"
            "Run in a second terminal:\n```\nuv run main.py --api\n```\n"
            "or start both at once:\n```\nuv run main.py --both\n```"
        )

    st.divider()

    if st.button("➕ Plan a New Trip", use_container_width=True, type="primary"):
        clear_plan_state()
        st.session_state.view_mode = "plan"
        st.rerun()

    trips = list_trips()
    if trips:
        st.markdown("**Your Trips**")
        for trip in trips:
            status, extra = get_trip_status(trip)
            if status == "active":
                badge = f"✈️ Day {extra}"
            elif status == "upcoming":
                badge = f"🗓️ In {extra}d"
            elif status == "past":
                badge = "✅ Done"
            else:
                badge = ""

            col1, col2 = st.columns([5, 1])
            with col1:
                btn_label = f"{trip['destination']}\n{badge}"
                if st.button(btn_label, key=f"load_{trip['trip_id']}", use_container_width=True):
                    loaded = load_trip(trip["trip_id"])
                    st.session_state.view_mode = "trip"
                    st.session_state.active_trip_id = trip["trip_id"]
                    st.session_state.trip_data = loaded
                    st.session_state.messages = loaded.get("messages", [])
                    st.session_state.itinerary_generated = True
                    st.session_state.companion_mode = False
                    st.rerun()
            with col2:
                if st.button("🗑️", key=f"del_{trip['trip_id']}"):
                    delete_trip(trip["trip_id"])
                    if st.session_state.get("active_trip_id") == trip["trip_id"]:
                        st.session_state.view_mode = "home"
                        clear_plan_state()
                    st.rerun()

# ── Session defaults ──────────────────────────────────────────────────────────────
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "home"
if "ask_marco_key" not in st.session_state:
    st.session_state.ask_marco_key = 0
if "messages" not in st.session_state:
    st.session_state.messages = []

# ═════════════════════════════════════════════════════════════════════════════════
# HOME VIEW
# ═════════════════════════════════════════════════════════════════════════════════
if st.session_state.view_mode == "home":
    trips = list_trips()

    if not trips:
        _, center, _ = st.columns([1, 2, 1])
        with center:
            st.markdown("## Welcome to Trip Companion")
            st.markdown(
                "Plan your next adventure with **Marco** — an AI travel expert who's visited "
                "70+ countries and gives brutally honest advice."
            )
            st.divider()
            if st.button("Plan Your First Trip →", type="primary", use_container_width=True):
                st.session_state.view_mode = "plan"
                st.rerun()
    else:
        st.title("Your Trips")
        cols = st.columns(3)
        for i, trip in enumerate(trips):
            status, extra = get_trip_status(trip)
            with cols[i % 3]:
                with st.container(border=True):
                    st.subheader(f"📍 {trip['destination']}")
                    st.caption(trip.get("dates", ""))
                    if status == "active":
                        st.success(f"✈️ Active — Day {extra} today")
                    elif status == "upcoming":
                        st.info(f"🗓️ Starts in {extra} days")
                    elif status == "past":
                        st.caption("✅ Completed")

                    if st.button("Open", key=f"open_{trip['trip_id']}", use_container_width=True):
                        loaded = load_trip(trip["trip_id"])
                        st.session_state.view_mode = "trip"
                        st.session_state.active_trip_id = trip["trip_id"]
                        st.session_state.trip_data = loaded
                        st.session_state.messages = loaded.get("messages", [])
                        st.session_state.itinerary_generated = True
                        st.session_state.companion_mode = False
                        st.rerun()

# ═════════════════════════════════════════════════════════════════════════════════
# PLAN VIEW
# ═════════════════════════════════════════════════════════════════════════════════
elif st.session_state.view_mode == "plan":
    _, center, _ = st.columns([0.5, 3, 0.5])
    with center:
        st.title("Plan Your Trip")
        st.caption("Fill in the details — Marco will build your full itinerary in one shot.")
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            destination = st.text_input(
                "Where are you going?",
                placeholder="e.g. Barcelona, Spain"
            )
        with col2:
            origin = st.text_input(
                "Traveling from?",
                placeholder="e.g. Amsterdam (for flight search)"
            )

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            start_date = st.date_input("From", value=date.today() + timedelta(days=30))
        with col2:
            end_date = st.date_input("To", value=date.today() + timedelta(days=35))
        with col3:
            duration = max((end_date - start_date).days + 1, 1)
            st.metric("Days", duration)

        col1, col2 = st.columns(2)
        with col1:
            budget = st.number_input(
                "Total budget",
                min_value=100, max_value=500000,
                value=1000, step=100
            )
        with col2:
            currency = st.selectbox(
                "Currency",
                ["EUR", "USD", "GBP", "INR", "AUD", "CAD", "CHF", "JPY", "SGD"]
            )

        styles = st.multiselect(
            "Travel style (pick all that fit)",
            ["Adventure & Outdoors", "Culture & History", "Food & Drink",
             "Nature & Hiking", "Nightlife & Bars", "Art & Museums",
             "Beaches & Relaxation", "Shopping", "Off the beaten path"]
        )

        col1, col2 = st.columns(2)
        with col1:
            diet = st.multiselect(
                "Dietary preferences",
                ["No restrictions", "Vegetarian", "Vegan",
                 "Halal", "Kosher", "Gluten-free"],
                default=["No restrictions"]
            )
        with col2:
            has_license = st.radio(
                "Driver's license?",
                ["Yes", "No"],
                horizontal=True
            )

        special = st.text_area(
            "Anything Marco should know?",
            placeholder="e.g. bad knee, travelling for a birthday, hate tourist traps, need wheelchair access...",
            height=80
        )

        submitted = st.button(
            "Generate My Trip Plan →",
            use_container_width=True,
            type="primary"
        )

        if submitted:
            if not destination:
                st.error("Please enter a destination.")
            elif end_date <= start_date:
                st.error("End date must be after start date.")
            else:
                style_str = ", ".join(styles) if styles else "Open to anything"
                diet_str = ", ".join(diet) if diet else "No restrictions"

                prompt = f"""Plan my trip with these details:
- Destination: {destination}
- Traveling from: {origin or 'not specified'}
- Dates: {start_date} to {end_date} ({duration} days)
- Total budget: {budget} {currency}
- Travel style: {style_str}
- Dietary preferences: {diet_str}
- Driver's license: {has_license}"""
                if special.strip():
                    prompt += f"\n- Notes: {special.strip()}"
                prompt += "\n\nPlease generate a complete day-by-day itinerary."

                st.session_state.messages = [{"role": "user", "content": prompt}]
                st.session_state.trip_data = {
                    "destination": destination,
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "dates": f"{start_date} to {end_date}",
                    "budget": float(budget),
                    "currency": currency,
                }
                st.session_state.itinerary_generated = False
                st.session_state.companion_mode = False
                st.session_state.view_mode = "trip"
                st.session_state.pop("active_trip_id", None)
                st.rerun()

# ═════════════════════════════════════════════════════════════════════════════════
# TRIP VIEW
# ═════════════════════════════════════════════════════════════════════════════════
elif st.session_state.view_mode == "trip":
    trip_data = st.session_state.get("trip_data", {})
    messages = st.session_state.get("messages", [])
    status, extra = get_trip_status(trip_data)

    # ── Rebuild Today (triggered by button on previous render) ────────────────────
    if st.session_state.get("rebuilding_day"):
        day_num = st.session_state.pop("rebuilding_day")
        city = trip_data.get("city") or trip_data.get("destination", "")
        rebuild_prompt = (
            f"Rebuild Day {day_num}'s itinerary based on today's actual weather in {city}. "
            f"Use the weather tool to check current conditions, then restructure: if rain or "
            f"bad weather is forecast, move outdoor activities to better windows or swap them "
            f"for indoor alternatives. Keep the same neighbourhood and general vibe. "
            f"Output ONLY the rebuilt day plan, starting with 'Day {day_num} — [New Title]'. "
            f"No preamble, no commentary."
        )
        rebuild_msgs = messages + [{"role": "user", "content": rebuild_prompt}]
        st.markdown(f"### 🔄 Rebuilding Day {day_num} around today's weather...")
        _rb_status = st.empty()
        rebuilt = st.write_stream(api.chat_stream(
            rebuild_msgs,
            trip_data=trip_data,
            companion_mode=True,
            on_tool_call=_make_tool_status_callback(_rb_status),
        ))
        _rb_status.empty()
        overrides = dict(trip_data.get("day_overrides") or {})
        overrides[str(day_num)] = rebuilt
        updated_trip = {**trip_data, "day_overrides": overrides, "messages": messages}
        _tid = st.session_state.get("active_trip_id")
        if _tid:
            api.update_trip(_tid, updated_trip)
        st.session_state.trip_data = updated_trip
        st.rerun()

    # ── Header ───────────────────────────────────────────────────────────────────
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title(f"📍 {trip_data.get('destination', 'Your Trip')}")
        st.caption(trip_data.get("dates", ""))
    with col2:
        if status == "active":
            st.success(f"✈️ Active — Day {extra}")
        elif status == "upcoming":
            st.info(f"🗓️ Starts in {extra} days")
        elif status == "past":
            st.caption("✅ Completed")

    # ── Budget card ───────────────────────────────────────────────────────────
    breakdown = trip_data.get("budget_breakdown") or {}
    total_budget = trip_data.get("budget")
    currency = trip_data.get("currency", "EUR")

    if total_budget or breakdown:
        with st.expander("💰 Budget Overview", expanded=False):
            categories = {
                "flights": "✈️ Flights",
                "accommodation": "🏨 Accommodation",
                "food": "🍽️ Food",
                "activities": "🎒 Activities",
                "transport": "🚌 Local Transport",
            }
            visible = {k: v for k, v in breakdown.items() if k in categories and v}
            if visible:
                cols = st.columns(len(visible))
                for col, (key, label) in zip(cols, ((k, categories[k]) for k in visible)):
                    col.metric(label, f"{currency} {visible[key]:,.0f}")

            total_estimated = breakdown.get("total_estimated")
            row = st.columns(2)
            if total_budget:
                row[0].metric("Total Budget", f"{currency} {total_budget:,.0f}")
            if total_estimated:
                delta = total_budget - total_estimated if total_budget else None
                delta_str = f"{currency} {abs(delta):,.0f} {'under' if delta >= 0 else 'over'}" if delta is not None else None
                row[1].metric("Marco's Estimate", f"{currency} {total_estimated:,.0f}",
                              delta=delta_str,
                              delta_color="normal" if not delta or delta >= 0 else "inverse")
                if delta is not None and delta < 0:
                    overage = abs(delta)
                    st.warning(
                        f"⚠️ Marco's estimate is **{currency} {overage:,.0f} over your budget**. "
                        f"Open **Ask Marco** below and ask him to find cheaper flights or hotels."
                    )
            elif not visible:
                st.caption("Budget breakdown will appear after your itinerary is generated.")

    st.divider()

    # ── Generate itinerary (fresh plan from form) ─────────────────────────────
    if not st.session_state.get("itinerary_generated", True) and len(messages) == 1:
        tool_status = st.empty()
        with st.chat_message("assistant", avatar="🧭"):
            response = st.write_stream(api.chat_stream(
                messages,
                trip_data=trip_data,
                on_tool_call=_make_tool_status_callback(tool_status),
            ))
        tool_status.empty()

        messages.append({"role": "assistant", "content": response})
        st.session_state.messages = messages
        st.session_state.itinerary_generated = True

        # Auto-extract details + budget breakdown via a single API call (2 Haiku calls server-side)
        with st.spinner("Saving your trip..."):
            info = api.extract_info(messages, currency=trip_data.get("currency", "EUR"))

        merged = {
            **trip_data,
            "destination": info.get("destination") or trip_data.get("destination", ""),
            "city": info.get("city", ""),
            "country_code": info.get("country_code", ""),
            "start_date": info.get("start_date") or trip_data.get("start_date", ""),
            "end_date": info.get("end_date") or trip_data.get("end_date", ""),
            "dates": trip_data.get("dates", ""),
            "messages": messages,
            "budget_breakdown": info.get("budget_breakdown", {}),
        }
        trip_id = save_trip(merged)
        st.session_state.active_trip_id = trip_id
        st.session_state.trip_data = load_trip(trip_id)
        st.rerun()

    # ── Day-by-day itinerary ──────────────────────────────────────────────────
    itinerary = extract_itinerary(messages)
    days = extract_all_days(itinerary)
    day_overrides = trip_data.get("day_overrides") or {}

    if days:
        for day_data in days:
            is_today = (status == "active" and day_data["day"] == extra)
            has_override = str(day_data["day"]) in day_overrides
            label = day_data["title"]
            if is_today:
                label = f"📍 {label}  ← today"
            if has_override:
                label += "  🔄 rebuilt"
            with st.expander(label, expanded=is_today):
                st.markdown(day_overrides.get(str(day_data["day"]), day_data["content"]))
    elif itinerary:
        st.markdown(itinerary)
    else:
        st.info("No itinerary yet — something went wrong during generation.")

    st.divider()

    # ── Action buttons ────────────────────────────────────────────────────────
    def _build_export_markdown() -> str:
        dest = trip_data.get("destination", "Trip")
        bgt = trip_data.get("budget")
        cur = trip_data.get("currency", "")
        header = f"# {dest}\n**Dates:** {trip_data.get('dates', '')}"
        if bgt:
            header += f"  |  **Budget:** {cur} {bgt:,.0f}"
        return f"{header}\n\n---\n\n{itinerary}" if itinerary else header

    def _build_ics() -> str:
        """iCalendar file — one all-day event per trip day."""
        def _esc(s: str) -> str:
            return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
        lines = [
            "BEGIN:VCALENDAR", "VERSION:2.0",
            "PRODID:-//Solo Travel Agent//Marco//EN",
            "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        ]
        try:
            start_obj = date.fromisoformat(trip_data.get("start_date", ""))
            tid = trip_data.get("trip_id", "trip")
            for d in days:
                day_date = start_obj + timedelta(days=d["day"] - 1)
                title = re.sub(r"[#*`_]", "", d["title"]).strip()
                desc  = re.sub(r"[#*`_]", "", d["content"])[:400].replace("\n", " ").strip()
                lines += [
                    "BEGIN:VEVENT",
                    f"DTSTART;VALUE=DATE:{day_date.strftime('%Y%m%d')}",
                    f"DTEND;VALUE=DATE:{(day_date + timedelta(days=1)).strftime('%Y%m%d')}",
                    f"SUMMARY:{_esc(trip_data.get('destination','') + ' — ' + title)}",
                    f"DESCRIPTION:{_esc(desc)}",
                    f"UID:{tid}-day{d['day']}@solo-travel-agent",
                    "END:VEVENT",
                ]
        except (ValueError, TypeError):
            pass
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)

    def _build_offline_html() -> str:
        """Self-contained HTML — works without internet, dark-mode aware."""
        dest  = trip_data.get("destination", "Trip")
        bgt   = trip_data.get("budget")
        cur   = trip_data.get("currency", "")
        meta  = trip_data.get("dates", "")
        if bgt:
            meta += f"  ·  Budget: {cur} {bgt:,.0f}"

        blocks = ""
        for d in days:
            content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", d["content"])
            content = re.sub(r"^#{1,3}\s*(.+)$", r"<h3>\1</h3>", content, flags=re.MULTILINE)
            content = content.replace("\n\n", "</p><p>").replace("\n", "<br>")
            title   = re.sub(r"[#*`_]", "", d["title"]).strip()
            blocks += f'<details><summary>{title}</summary><div class="body"><p>{content}</p></div></details>\n'

        return f"""<!DOCTYPE html>
<html lang="en"><head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{dest}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:780px;margin:0 auto;padding:20px;color:#1a1a2e}}
    h1{{font-size:1.6rem;margin-bottom:4px}} .meta{{color:#666;font-size:.9rem;margin-bottom:24px}}
    details{{border:1px solid #e0e0e0;border-radius:10px;margin-bottom:10px;overflow:hidden}}
    summary{{padding:14px 16px;font-weight:600;cursor:pointer;background:#f8f9fa;user-select:none}}
    summary:hover{{background:#e9ecef}}
    .body{{padding:16px;line-height:1.75;font-size:.95rem}} .body p{{margin-bottom:12px}}
    h3{{margin:12px 0 6px;font-size:1rem;color:#444}} strong{{color:#1a1a2e}}
    footer{{margin-top:40px;color:#aaa;font-size:.75rem;text-align:center}}
    @media(prefers-color-scheme:dark){{
      body{{background:#121212;color:#e0e0e0}} details{{border-color:#333}}
      summary{{background:#1e1e1e}} strong{{color:#e0e0e0}} h3{{color:#bbb}}
    }}
  </style>
</head><body>
  <h1>📍 {dest}</h1><p class="meta">{meta}</p>
  {blocks}
  <footer>Generated by Trip Companion · Works offline</footer>
</body></html>"""

    dest_slug = trip_data.get("destination", "trip").replace(",", "").replace(" ", "_").lower()

    if status == "active":
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            if st.button(
                f"🧭 I'm on Day {extra} — What should I do?",
                use_container_width=True, type="primary",
            ):
                st.session_state.companion_mode = True
                st.session_state.messages.append({
                    "role": "user",
                    "content": f"Hey Marco, I'm on Day {extra} of my trip in {trip_data.get('destination')}. What should I focus on today?"
                })
                st.rerun()
        with col2:
            if itinerary and st.button("🔄 Rebuild Today", use_container_width=True,
                                       help="Regenerate today's plan around current weather"):
                st.session_state["rebuilding_day"] = extra
                st.rerun()
        with col3:
            if st.button("↺ Regenerate Plan", use_container_width=True,
                         help="Rebuild the entire itinerary from scratch"):
                if messages:
                    st.session_state.messages = [messages[0]]
                    st.session_state.itinerary_generated = False
                    st.rerun()
    else:
        if st.button("↺ Regenerate Plan", help="Rebuild the entire itinerary from scratch"):
            if messages:
                st.session_state.messages = [messages[0]]
                st.session_state.itinerary_generated = False
                st.rerun()

    if itinerary:
        with st.expander("📤 Export & Share"):
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                st.download_button(
                    "📝 Markdown",
                    data=_build_export_markdown(),
                    file_name=f"{dest_slug}_itinerary.md",
                    mime="text/markdown",
                    use_container_width=True,
                    help="For Notion, Obsidian, or any notes app",
                )
            with ec2:
                st.download_button(
                    "📅 Calendar (.ics)",
                    data=_build_ics(),
                    file_name=f"{dest_slug}_trip.ics",
                    mime="text/calendar",
                    use_container_width=True,
                    help="Import into Google Calendar, Apple Calendar, or Outlook",
                )
            with ec3:
                st.download_button(
                    "📱 Offline HTML",
                    data=_build_offline_html(),
                    file_name=f"{dest_slug}_trip.html",
                    mime="text/html",
                    use_container_width=True,
                    help="Save to your phone — no internet needed on the trip",
                )

    st.divider()

    # ── Ask Marco ─────────────────────────────────────────────────────────────
    companion_mode = st.session_state.get("companion_mode", False)
    with st.expander("💬 Ask Marco", expanded=companion_mode):
        # Show only follow-up conversation — itinerary is shown in day cards above
        display_messages = messages[2:]

        for msg in display_messages:
            avatar = "🧭" if msg["role"] == "assistant" else "🧳"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

        col1, col2 = st.columns([5, 1])
        with col1:
            user_input = st.text_input(
                "Ask Marco",
                placeholder="Ask anything about this trip...",
                label_visibility="collapsed",
                key=f"ask_marco_input_{st.session_state.ask_marco_key}"
            )
        with col2:
            send = st.button("Send", use_container_width=True)

        if send and user_input.strip():
            new_messages = st.session_state.messages + [
                {"role": "user", "content": user_input.strip()}
            ]
            st.session_state.messages = new_messages

            with st.chat_message("user", avatar="🧳"):
                st.markdown(user_input.strip())

            active_trip = st.session_state.get("trip_data")
            tool_status = st.empty()
            with st.chat_message("assistant", avatar="🧭"):
                response = st.write_stream(api.chat_stream(
                    new_messages,
                    trip_data=active_trip,
                    companion_mode=companion_mode,
                    on_tool_call=_make_tool_status_callback(tool_status),
                ))
            tool_status.empty()

            st.session_state.messages.append({"role": "assistant", "content": response})

            # Persist updated conversation to saved trip
            trip_id = st.session_state.get("active_trip_id")
            if trip_id:
                saved = load_trip(trip_id)
                if saved:
                    saved["messages"] = st.session_state.messages
                    update_trip(trip_id, saved)

            st.session_state.ask_marco_key += 1
            st.rerun()
