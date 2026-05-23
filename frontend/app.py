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

    if days:
        for day_data in days:
            is_today = (status == "active" and day_data["day"] == extra)
            label = f"📍 {day_data['title']}  ← today" if is_today else day_data["title"]
            with st.expander(label, expanded=is_today):
                st.markdown(day_data["content"])
    elif itinerary:
        st.markdown(itinerary)
    else:
        st.info("No itinerary yet — something went wrong during generation.")

    st.divider()

    # ── Action buttons ────────────────────────────────────────────────────────
    def _build_export_markdown() -> str:
        """Build a markdown export of the full trip."""
        dest = trip_data.get("destination", "Trip")
        dates = trip_data.get("dates", "")
        bgt = trip_data.get("budget")
        cur = trip_data.get("currency", "")
        header = f"# {dest}\n**Dates:** {dates}"
        if bgt:
            header += f"  |  **Budget:** {cur} {bgt:,.0f}"
        return f"{header}\n\n---\n\n{itinerary}" if itinerary else header

    if status == "active":
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            if st.button(
                f"🧭 I'm on Day {extra} — What should I do?",
                use_container_width=True,
                type="primary"
            ):
                st.session_state.companion_mode = True
                st.session_state.messages.append({
                    "role": "user",
                    "content": f"Hey Marco, I'm on Day {extra} of my trip in {trip_data.get('destination')}. What should I focus on today?"
                })
                st.rerun()
        with col2:
            if st.button("🔄 Regenerate Plan", use_container_width=True):
                if messages:
                    st.session_state.messages = [messages[0]]
                    st.session_state.itinerary_generated = False
                    st.rerun()
        with col3:
            if itinerary:
                dest_slug = trip_data.get("destination", "trip").replace(",", "").replace(" ", "_").lower()
                st.download_button(
                    "📥 Export Itinerary",
                    data=_build_export_markdown(),
                    file_name=f"{dest_slug}_itinerary.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
    else:
        col1, col2 = st.columns([2, 2])
        with col1:
            if st.button("🔄 Regenerate Plan", use_container_width=True):
                if messages:
                    st.session_state.messages = [messages[0]]
                    st.session_state.itinerary_generated = False
                    st.rerun()
        with col2:
            if itinerary:
                dest_slug = trip_data.get("destination", "trip").replace(",", "").replace(" ", "_").lower()
                st.download_button(
                    "📥 Export Itinerary",
                    data=_build_export_markdown(),
                    file_name=f"{dest_slug}_itinerary.md",
                    mime="text/markdown",
                    use_container_width=True,
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
