import os
import re
import json
from datetime import date, datetime
from anthropic import Anthropic
from dotenv import load_dotenv
from backend.agents.tools import TOOL_DEFINITIONS
from backend.agents.tool_executor import execute_tool
from backend.tools.weather import get_weather_forecast, format_weather_for_marco
from backend.config import (
    SONNET_MODEL,
    HAIKU_MODEL,
    PLANNING_MAX_TOKENS,
    COMPANION_MAX_TOKENS,
    EXTRACTION_MAX_TOKENS,
)


def _log_claude_usage(model: str, usage) -> None:
    try:
        from backend.db.database import SessionLocal
        from backend.db.models import ClaudeUsageLog
        with SessionLocal() as session:
            session.add(ClaudeUsageLog(
                model=model,
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
                cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            ))
            session.commit()
    except Exception:
        pass

load_dotenv()

client = Anthropic()


def load_prompt(filename: str) -> str:
    """Load a prompt from the prompts directory."""
    prompts_dir = os.path.join(os.path.dirname(__file__), '..', 'prompts')
    filepath = os.path.join(prompts_dir, filename)
    with open(filepath, 'r') as f:
        return f.read()


SYSTEM_PROMPT = load_prompt("marco.md")

_INJECT_RE = re.compile(r"(##\s|ignore\s|system\s*prompt|<\s*/?system|instruction)", re.IGNORECASE)

def _safe_str(value: str, max_len: int = 200) -> str:
    """Sanitize a client-supplied string before injecting it into the system prompt.
    Strips leading/trailing whitespace, truncates, and rejects values that look
    like prompt-injection attempts (returns empty string in that case).
    """
    s = str(value).strip()[:max_len]
    if _INJECT_RE.search(s):
        return ""
    return s


def extract_trip_details(messages: list) -> dict:
    """Use Claude Haiku to extract structured trip details from conversation."""
    conversation = "\n".join(
        f"{m['role'].upper()}: {m['content'][:600]}"
        for m in messages
    )

    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=EXTRACTION_MAX_TOKENS,
            system="""Extract trip details from a travel planning conversation.
Return ONLY a JSON object with these exact fields:
- destination: descriptive trip name (e.g. "Kraków, Poland", "Austrian Alps")
- city: main city for weather lookup (e.g. "Kraków", "Salzburg")
- country_code: 2-letter ISO code (e.g. "PL", "AT", "ES")
- start_date: YYYY-MM-DD format, or "" if not mentioned
- end_date: YYYY-MM-DD format, or "" if not mentioned
- budget: the user's most recently stated budget as a plain number (e.g. 35000), or null if not mentioned. Use the LATEST value if the user updated it.

No markdown, no explanation. JSON object only.""",
            messages=[
                {"role": "user", "content": f"Extract trip details:\n\n{conversation}"}
            ]
        )
        _log_claude_usage(HAIKU_MODEL, response.usage)
        raw = response.content[0].text.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except Exception:
        return {}


def extract_structured_itinerary(itinerary: str, currency: str = "EUR") -> dict:
    """
    Use Haiku with tool_choice to extract a typed day-by-day plan + budget in one call.

    Forcing tool use guarantees the model returns the exact schema — no JSON
    parsing fragility, no regex, no missed fields.

    Returns {"days": [...], "budget_breakdown": {...}} or {} on failure.
    """
    if not itinerary:
        return {}

    _tool = {
        "name": "save_itinerary",
        "description": "Persist the structured itinerary with day plans and budget breakdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "array",
                    "description": "Every day section from the itinerary, in order.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "day": {
                                "type": "integer",
                                "description": (
                                    "Day number as an integer. "
                                    "For ranges like 'Day 5-6' use the first number (5)."
                                ),
                            },
                            "title": {
                                "type": "string",
                                "description": (
                                    "Descriptive title only — strip the 'Day N', 'Day N:', "
                                    "or 'Day N — ' prefix and any leading date. "
                                    "e.g. from '## Day 1 — Arrival & Gentle Start' extract 'Arrival & Gentle Start'."
                                ),
                            },
                            "content": {
                                "type": "string",
                                "description": "Complete text for this day (activities, meals, tips, etc.).",
                            },
                        },
                        "required": ["day", "title", "content"],
                    },
                },
                "budget_breakdown": {
                    "type": "object",
                    "description": f"Estimated total costs in {currency} for the whole trip.",
                    "properties": {
                        "flights": {
                            "type": ["number", "null"],
                            "description": (
                                "Total flight costs. Use 0 if flights are mentioned but free/included; "
                                "null only if flights are completely absent from the plan."
                            ),
                        },
                        "accommodation": {"type": ["number", "null"], "description": "Total accommodation costs."},
                        "food": {"type": ["number", "null"], "description": "Total food & dining costs."},
                        "activities": {"type": ["number", "null"], "description": "Total activity & entrance-fee costs."},
                        "transport": {"type": ["number", "null"], "description": "Local transport costs (taxis, trains, buses)."},
                        "total_estimated": {"type": ["number", "null"], "description": "Sum of all estimated costs."},
                    },
                },
            },
            "required": ["days", "budget_breakdown"],
        },
    }

    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=8096,
            tools=[_tool],
            tool_choice={"type": "tool", "name": "save_itinerary"},
            system=(
                f"You are a travel itinerary parser. "
                f"Extract every day section and the budget estimate (in {currency}) "
                f"from the itinerary below. Preserve the full content for each day."
            ),
            messages=[{"role": "user", "content": itinerary[:8000]}],
        )
        _log_claude_usage(HAIKU_MODEL, response.usage)
        for block in response.content:
            if hasattr(block, "type") and block.type == "tool_use":
                return block.input
    except Exception as exc:
        print(f"extract_structured_itinerary error: {exc}")
    return {}


def extract_itinerary(messages: list) -> str:
    """Pull the full itinerary text from saved conversation history.

    Prefers the last assistant message that has proper Day N headers (i.e. a
    real day-by-day plan), falling back to the last message that merely
    mentions "day 1".  This prevents later conversational replies that
    casually reference "Day 1" from shadowing the actual itinerary.
    """
    # Allow optional non-word chars (emojis, icons) between ### and Day N
    heading_re = re.compile(r'(?i)(?:^|\n)[ \t]*(?:#{1,3}[ \t]*[^\w\n]*[ \t]*)?\*{0,2}day[ \t]+\d+')

    def _is_real_itinerary(content: str) -> bool:
        return len(heading_re.findall(content)) >= 2

    candidates = [m for m in reversed(messages) if m["role"] == "assistant"]

    # Prefer a message with actual day-structure headings
    for m in candidates:
        if _is_real_itinerary(m["content"]):
            return m["content"]

    # Fallback: last assistant message that mentions "day 1" at all
    for m in candidates:
        if "day 1" in m["content"].lower():
            return m["content"]

    return ""


def extract_day_section(itinerary: str, day_number: int) -> str:
    """Extract a specific day's section from the full itinerary text."""
    pattern = re.compile(
        rf'(?i)((?:#{1,3}\s*)?\*{{0,2}}DAY\s+{day_number}\b.*?)(?=(?:#{1,3}\s*)?\*{{0,2}}DAY\s+\d+|\Z)',
        re.DOTALL
    )
    match = pattern.search(itinerary)
    return match.group(1).strip() if match else ""


def extract_all_days(itinerary: str) -> list[dict]:
    """Split itinerary into individual day sections for structured display."""
    # Matches day headings in any format Marco produces, e.g.:
    #   ### **DAY 1 (May 28) — ARRIVAL & GENTLE START**
    #   ### **DAY 5-6 (June 1-2) — HAMPI ESCAPE**
    #   **Day 3:** Culture day
    # Key additions over the original pattern:
    #   (?:-\d+)?       — handles day ranges like "5-6"
    #   (?:\s*\([^)]*\))?  — handles parenthetical dates like "(May 28)"
    heading_pattern = re.compile(
        r'(?im)^([ \t]*(?:#{1,3}[ \t]*[^\w\n]*[ \t]*)?\*{0,2}(?:DAY|Day)[ \t]+(\d+)(?:-\d+)?(?:\*{0,2})?(?:\s*\([^)]*\))?[ \t]*(?:[-—–:][^\n]*)?)$'
    )
    matches = list(heading_pattern.finditer(itinerary))
    if not matches:
        return []

    # Keep only the first occurrence of each day number to avoid duplicates
    seen: set[int] = set()
    unique_matches = []
    for match in matches:
        day_num = int(match.group(2))
        if day_num not in seen:
            seen.add(day_num)
            unique_matches.append(match)

    days = []
    for i, match in enumerate(unique_matches):
        day_num = int(match.group(2))
        raw_title = match.group(1)
        clean_title = re.sub(r'[#*]+', '', raw_title).strip()
        clean_title = re.sub(r'\s+', ' ', clean_title)

        start = match.start()
        end = unique_matches[i + 1].start() if i + 1 < len(unique_matches) else len(itinerary)
        content = itinerary[start:end].strip()

        days.append({"day": day_num, "title": clean_title, "content": content})

    return days


def get_trip_day(start_date_str: str, end_date_str: str) -> dict:
    """
    Given saved trip dates, calculate which day of the trip today is.
    Returns a dict with status and day info.
    """
    today = date.today()

    try:
        start_date = date.fromisoformat(start_date_str)
        end_date = date.fromisoformat(end_date_str)
    except (ValueError, TypeError):
        return {"status": "unknown"}

    if today < start_date:
        return {
            "status": "upcoming",
            "days_until": (start_date - today).days,
            "start_date": start_date_str,
            "end_date": end_date_str,
        }
    elif start_date <= today <= end_date:
        day_number = (today - start_date).days + 1
        total_days = (end_date - start_date).days + 1
        return {
            "status": "active",
            "day_number": day_number,
            "total_days": total_days,
            "start_date": start_date_str,
            "end_date": end_date_str,
            "todays_date": today.isoformat(),
        }
    else:
        return {
            "status": "past",
            "start_date": start_date_str,
            "end_date": end_date_str,
        }


def run_agentic_loop(messages: list, system: str | list, on_tool_call=None, collected: dict | None = None, model: str | None = None, max_tokens: int | None = None):
    """
    Core agentic loop — handles tool use automatically.
    Yields text chunks as they stream from Claude.

    Args:
        messages:     Conversation history (list of role/content dicts).
        system:       System prompt — either a plain string or a list of content
                      blocks (supports cache_control for prompt caching).
        on_tool_call: Optional callable(tool_name: str, tool_input: dict) fired
                      just before each tool is executed. Use it to surface live
                      progress in a UI (e.g., update an st.empty() container).
        collected:    Optional mutable dict; tool results (e.g. hotel suggestions)
                      are written here so callers can surface them in the UI.
        model:        Override the model. Defaults to SONNET_MODEL.
        max_tokens:   Override max output tokens. Defaults to PLANNING_MAX_TOKENS.
    """

    _model = model or SONNET_MODEL
    _max_tokens = max_tokens or PLANNING_MAX_TOKENS
    current_messages = messages.copy()

    while True:
        with client.messages.stream(
            model=_model,
            max_tokens=_max_tokens,
            system=system,
            tools=TOOL_DEFINITIONS,
            messages=current_messages
        ) as stream:
            for text in stream.text_stream:
                yield text

            final_message = stream.get_final_message()
            _log_claude_usage(_model, final_message.usage)

        if final_message.stop_reason == "end_turn":
            return

        if final_message.stop_reason == "tool_use":
            current_messages.append({
                "role": "assistant",
                "content": final_message.content
            })

            tool_results = []

            for block in final_message.content:
                if block.type == "tool_use":
                    print(f"🔧 Marco is using tool: {block.name} with {block.input}")
                    if on_tool_call is not None:
                        on_tool_call(block.name, block.input)
                    result = execute_tool(block.name, block.input, collected=collected)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            current_messages.append({
                "role": "user",
                "content": tool_results
            })

        else:
            return


def chat(messages: list, trip_data: dict = None, companion_mode: bool = False, on_tool_call=None, collected: dict | None = None):
    """Send a message to Marco and get a streaming response."""

    today = datetime.now().strftime("%A, %B %d, %Y")
    user_currency = (trip_data or {}).get("currency", "EUR")
    num_travelers = int((trip_data or {}).get("number_of_travelers") or 1)
    dynamic_context = (
        f"\n\n## Current Date\nToday is {today}."
        f"\n\n## User Currency\nThe user's selected currency is **{user_currency}**. "
        f"Always pass `currency: \"{user_currency}\"` when calling search_flights. "
        f"Show all prices in {user_currency} — never convert or mention another currency."
    )
    if num_travelers > 1:
        dynamic_context += (
            f"\n\n## Group Size\nThis trip is for a **group of {num_travelers} people**. "
            f"The stated budget is **per person** — do not multiply it. "
            f"Account for group logistics: shared accommodation options, group-friendly venues, "
            f"and activities that work for {num_travelers} people traveling together."
        )

    if companion_mode and trip_data:
        trip_day = get_trip_day(
            trip_data.get("start_date", ""),
            trip_data.get("end_date", "")
        )

        if trip_day["status"] == "active":
            day_number = trip_day["day_number"]
            total_days = trip_day["total_days"]

            # Extract today's plan from the saved itinerary
            itinerary = extract_itinerary(trip_data.get("messages", []))
            today_plan = extract_day_section(itinerary, day_number)

            # Always fetch weather server-side — never trust client-supplied weather_text
            # since it lands verbatim in the system prompt (prompt-injection vector).
            # Results are disk-cached (1-hour TTL) so this is not an extra API call.
            city = trip_data.get("city") or trip_data.get("destination", "")
            country_code = trip_data.get("country_code", "")
            weather_text = ""
            if city:
                try:
                    weather_data = get_weather_forecast(city, country_code)
                    weather_text = format_weather_for_marco(weather_data)
                except Exception:
                    pass

            destination = _safe_str(trip_data.get("destination", ""))
            start_date  = _safe_str(trip_data.get("start_date",  ""))
            end_date    = _safe_str(trip_data.get("end_date",    ""))

            dynamic_context += f"""

## COMPANION MODE — ACTIVE TRIP
The user is CURRENTLY ON THIS TRIP. Today is Day {day_number} of {total_days}.
- Destination: {destination}
- Trip dates: {start_date} to {end_date}

Switch fully into companion mode: short, punchy, actionable. They're on their phone.
Lead with weather impact — what does today's forecast mean for the plan?
If weather is bad, restructure proactively. Don't just warn — give the fix.
Ask how yesterday went if it's Day 2+."""

            if today_plan:
                dynamic_context += f"""

## TODAY'S ITINERARY (Day {day_number})
{today_plan}"""

            if weather_text:
                dynamic_context += f"""

## CURRENT WEATHER (fetched live)
{weather_text}
Use this to adjust today's plan. Don't mention you fetched it — just act on it."""

    # Cache the static system prompt (marco.md) — it never changes between requests.
    # The dynamic block (date, companion context) is excluded from the cache since it
    # varies per request and would bust the cache on every call anyway.
    system = [
        {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": dynamic_context},
    ]

    model = HAIKU_MODEL if companion_mode else SONNET_MODEL
    tokens = COMPANION_MAX_TOKENS if companion_mode else PLANNING_MAX_TOKENS
    yield from run_agentic_loop(messages, system, on_tool_call=on_tool_call, collected=collected, model=model, max_tokens=tokens)

def generate_checklist(destination: str, passport_country: str, start_date: str) -> list[dict]:
    """
    Use Claude Haiku to generate a pre-trip checklist.

    Returns a list of dicts: [{category, item, priority}]
    Categories: visa, health, insurance, documents, kit
    Priorities: high | normal | low
    """
    prompt = f"""Generate a concise, context-aware pre-trip checklist for a solo traveller.

Destination: {destination}
Passport / citizenship country: {passport_country or "not specified"}
Departure date: {start_date or "soon"}

CRITICAL CONTEXT RULES — apply these before generating any item:
1. DOMESTIC TRAVEL: If the destination country matches the passport/citizenship country (e.g. Indian citizen → Ladakh/India, US citizen → New York, etc.) this is a DOMESTIC trip. For domestic travel:
   - Do NOT include visa items (no visa needed for domestic travel)
   - Do NOT suggest getting a local SIM card (they already have one)
   - Do NOT suggest exchanging currency (they already have local currency)
   - Do NOT mention passport validity for domestic travel (passport not required)
   - Do NOT suggest emergency copies of passport for simple domestic trips
   - Focus instead on: health precautions specific to the region, insurance, offline maps, region-specific kit
2. INTERNATIONAL TRAVEL: Include visa, passport validity, SIM card, currency, and entry requirement items.
3. ALTITUDE / TERRAIN: For high-altitude destinations (e.g. Ladakh, Tibet, Nepal, Andes, Alps) always include altitude sickness prevention as HIGH priority.
4. Be intelligent — don't generate boilerplate that doesn't apply. Each item must be genuinely useful for this specific traveller.

Return ONLY valid JSON — an array of objects, no prose, no markdown fences:
[
  {{"category": "health", "item": "Consult doctor about altitude sickness medication", "priority": "high"}},
  ...
]

Categories (only include relevant ones):
- visa: entry requirements, e-visa, on-arrival (SKIP for domestic travel)
- health: vaccinations, altitude sickness, medication, travel clinic
- insurance: travel insurance, medical evacuation cover
- documents: passport validity (international only), copies of essential docs, emergency contacts
- kit: power adaptor, offline maps, gear specific to destination climate/terrain

Keep each item under 12 words. Return 8-15 items total.
Priority MUST be one of: "high", "normal", "low". Do not use "medium" or any other value."""

    # Normalise any non-standard priority Haiku might return
    _PRIORITY_MAP = {"high": "high", "normal": "normal", "low": "low",
                     "medium": "normal", "moderate": "normal", "critical": "high"}

    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        _log_claude_usage(HAIKU_MODEL, response.usage)
        raw = response.content[0].text.strip()
        # Strip markdown fences if Haiku adds them
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        items = json.loads(raw)
        # Validate and normalise
        validated = []
        for item in items:
            if isinstance(item, dict) and "item" in item:
                raw_priority = item.get("priority", "normal").lower()
                validated.append({
                    "category": item.get("category", "documents"),
                    "item": item["item"],
                    "priority": _PRIORITY_MAP.get(raw_priority, "normal"),
                })
        return validated
    except Exception as exc:
        print(f"generate_checklist error: {exc}")
        # Return a minimal fallback checklist (domestic-aware)
        fallback = [{"category": "insurance", "item": "Purchase travel insurance", "priority": "high"}]
        if passport_country and destination:
            # Very rough domestic check — if the passport country name appears in the destination
            pc = passport_country.lower().strip()
            dest = destination.lower()
            is_domestic = pc in dest or dest in pc
        else:
            is_domestic = False
        if not is_domestic:
            fallback += [
                {"category": "documents", "item": "Check passport validity (6+ months)", "priority": "high"},
                {"category": "visa", "item": f"Check visa requirements for {destination}", "priority": "high"},
            ]
        return fallback


def extract_preferences(debrief_text: str) -> list[str]:
    """
    Use Haiku to extract 3-6 concrete travel preference signals from a post-trip debrief.
    Returns a list of short strings, e.g. ["Prefers street food over restaurants", ...].
    Falls back to [] on any error.
    """
    if not debrief_text:
        return []
    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": (
                    "Extract 3-6 specific travel preference signals from this post-trip debrief. "
                    "Each should be a short, concrete statement (under 10 words) about the traveller's likes, "
                    "dislikes, or patterns — things that should inform future trip planning.\n"
                    'Return ONLY a JSON array of strings. Example: '
                    '["Prefers local food markets over sit-down restaurants", '
                    '"Dislikes crowded tourist sites", '
                    '"Loves half-day hikes with a view"]\n\n'
                    f"Debrief:\n{debrief_text}"
                ),
            }],
        )
        _log_claude_usage(HAIKU_MODEL, response.usage)
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        result = json.loads(raw)
        return [str(p) for p in result if isinstance(p, str)]
    except Exception as exc:
        print(f"extract_preferences error: {exc}")
        return []


if __name__ == "__main__":
    test_messages = [
        {
            "role": "user",
            "content": "Hey, I want to plan a solo trip from Amsterdam to Barcelona in late May for 5 days with a budget of €800. Can you help and also check flights?"
        }
    ]
    result = "".join(chat(test_messages))
    print(result)