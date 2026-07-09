import os
import re
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from dotenv import load_dotenv
from backend import llm
from backend.agents.tools import TOOL_DEFINITIONS
from backend.agents.tool_executor import execute_tool
from backend.tools.weather import get_weather_forecast, format_weather_for_marco
from backend.config import (
    LLM_MODEL,
    LLM_FAST_MODEL,
    PLANNING_MAX_TOKENS,
    COMPANION_MAX_TOKENS,
    EXTRACTION_MAX_TOKENS,
)


def _log_usage(model: str, usage: dict) -> None:
    try:
        from backend.db.database import SessionLocal
        from backend.db.models import ClaudeUsageLog
        with SessionLocal() as session:
            session.add(ClaudeUsageLog(
                model=model,
                input_tokens=usage.get("input_tokens", 0) or 0,
                output_tokens=usage.get("output_tokens", 0) or 0,
                cache_read_tokens=usage.get("cache_read_tokens", 0) or 0,
                cache_creation_tokens=usage.get("cache_creation_tokens", 0) or 0,
            ))
            session.commit()
    except Exception:
        pass


load_dotenv()


def load_prompt(filename: str) -> str:
    prompts_dir = os.path.join(os.path.dirname(__file__), '..', 'prompts')
    filepath = os.path.join(prompts_dir, filename)
    with open(filepath, 'r') as f:
        return f.read()


SYSTEM_PROMPT = load_prompt("marco.md")

_EXTRACT_TRIP_SYSTEM = """Extract trip details from a travel planning conversation.
Call save_trip_details with every field. Use "" (or null where allowed) for anything not mentioned.
For budget: scan ALL user messages; if multiple amounts were stated, use the most recent.
For trip_type: "road_trip" if the user plans to drive their own/rented vehicle between multiple places; "multi_city" for multiple destinations without self-driving; otherwise "single_destination".
For stops: fill ONLY when the user explicitly names the places to visit in order — never invent a route yourself.
For destination on multi-stop trips: a concise route label (e.g. "Amsterdam → Ghent → Bruges") if stops are known, else "<Origin> road trip"."""

_EXTRACT_TRIP_TOOL = {
    "type": "function",
    "function": {
        "name": "save_trip_details",
        "description": "Persist structured trip details extracted from the conversation.",
        "parameters": {
            "type": "object",
            "properties": {
                "destination": {
                    "type": "string",
                    "description": 'Descriptive trip name (e.g. "Kraków, Poland", "Austrian Alps"), or "" if not mentioned.',
                },
                "city": {
                    "type": "string",
                    "description": 'Main city for weather lookup (e.g. "Kraków", "Salzburg").',
                },
                "country_code": {
                    "type": "string",
                    "description": '2-letter ISO code of the destination country (e.g. "PL", "AT", "ES").',
                },
                "origin_country": {
                    "type": "string",
                    "description": 'Full country name the user is travelling FROM (e.g. "India"), or "" if not mentioned.',
                },
                "origin_city": {
                    "type": "string",
                    "description": 'City the user is travelling FROM (e.g. "Amsterdam"), or "" if not mentioned.',
                },
                "is_domestic": {
                    "type": ["boolean", "null"],
                    "description": "true if origin and destination are the same country, false if different, null if unknown.",
                },
                "start_date": {
                    "type": "string",
                    "description": 'YYYY-MM-DD, or "" if not mentioned.',
                },
                "end_date": {
                    "type": "string",
                    "description": 'YYYY-MM-DD, or "" if not mentioned.',
                },
                "budget": {
                    "type": ["number", "null"],
                    "description": "Budget as a plain number (e.g. 50000). null only if never mentioned anywhere.",
                },
                "trip_type": {
                    "type": "string",
                    "enum": ["single_destination", "road_trip", "multi_city"],
                },
                "has_own_vehicle": {
                    "type": "boolean",
                    "description": "true if the user has (or will rent) their own car/bike for the trip.",
                },
                "stops": {
                    "type": "array",
                    "description": "Ordered stops ONLY if the user explicitly named them. Empty otherwise.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "city": {"type": "string"},
                            "country_code": {"type": "string", "description": "2-letter ISO"},
                            "nights": {"type": "integer", "description": "Nights at this stop if stated; 1 if unknown."},
                        },
                        "required": ["city", "nights"],
                    },
                },
            },
            "required": [
                "destination", "city", "country_code", "origin_country", "origin_city",
                "is_domestic", "start_date", "end_date", "budget",
                "trip_type", "has_own_vehicle", "stops",
            ],
        },
    },
}

_CHECKLIST_SYSTEM = """You are a pre-trip checklist generator. Your job is to return only the items a traveller would genuinely regret not having. If in doubt, leave it out.

RULES — apply every rule before generating any item:

1. DOMESTIC TRAVEL (destination country = passport country):
   - NEVER include: passport, visa, power adaptor, SIM card, currency exchange, yellow fever, malaria tablets (unless the specific region is a known risk zone)
   - Only include: insurance, booking confirmations, destination-specific kit, genuinely relevant health notes

2. INTERNATIONAL TRAVEL: include passport validity, visa, SIM card, currency.

3. DESTINATION TYPE — be brutally honest about what this place actually requires:
   - Well-developed tourist city (Udaipur, Jaipur, Bangkok, Lisbon, Tokyo): skip doctor visits, water purification, medical evacuation. These cities have pharmacies, hospitals, and clean hotels. One health item max, only if the season or region genuinely warrants it.
   - Remote / off-grid / adventure (Ladakh, rural Nepal, Amazon, Sahara): water purification, medical kit, doctor consult are appropriate.
   - High altitude (>3500m — Ladakh, Tibet, high Andes): altitude sickness item, HIGH priority.
   - Monsoon season: one practical wet-weather kit item is fine. Do not dramatise it.

4. THE CUT TEST — before adding any item, ask: "Would a sensible, experienced traveller actually need reminding of this?" If the answer is no, skip it.
   - Skip: generic advice anyone knows ("stay hydrated", "bring sunscreen", "keep documents safe")
   - Skip: items that don't apply to this specific destination/season/traveller
   - Skip: redundant items (don't list both "waterproof jacket" and "quick-dry clothes" unless both genuinely add value)

Call save_checklist with the final items.

Categories (only include if genuinely relevant):
- visa: entry requirements (SKIP for domestic)
- health: real health risk for this specific destination only
- insurance: always include one insurance item
- documents: booking confirmations; passport validity for international only
- kit: destination/season-specific gear only

Return 5-8 items total. Fewer is better. Every item must earn its place."""

_CHECKLIST_TOOL = {
    "type": "function",
    "function": {
        "name": "save_checklist",
        "description": "Persist the pre-trip checklist items.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["visa", "health", "insurance", "documents", "kit"],
                            },
                            "item": {
                                "type": "string",
                                "description": 'Concrete, destination-specific reminder (e.g. "Waterproof bag for electronics during monsoon").',
                            },
                            "priority": {"type": "string", "enum": ["high", "normal", "low"]},
                        },
                        "required": ["category", "item", "priority"],
                    },
                },
            },
            "required": ["items"],
        },
    },
}

_PREFERENCES_SYSTEM = """Extract 3-6 specific travel preference signals from the post-trip debrief provided.
Each signal should be a short, concrete statement (under 10 words) about the traveller's likes, dislikes, or patterns — things that should inform future trip planning.
Call save_preferences with the signals. Example signals: "Prefers local food markets over sit-down restaurants", "Dislikes crowded tourist sites"."""

_PREFERENCES_TOOL = {
    "type": "function",
    "function": {
        "name": "save_preferences",
        "description": "Persist extracted travel preference signals.",
        "parameters": {
            "type": "object",
            "properties": {
                "preferences": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-6 short preference statements, each under 10 words.",
                },
            },
            "required": ["preferences"],
        },
    },
}

_INJECT_RE = re.compile(r"(##\s|ignore\s|system\s*prompt|<\s*/?system|instruction)", re.IGNORECASE)
_WEATHER_CITY_ALIASES = {
    ("Bali, Indonesia", "Bali"): "Denpasar",
}

def _safe_str(value: str, max_len: int = 200) -> str:
    s = str(value).strip()[:max_len]
    if _INJECT_RE.search(s):
        return ""
    return s


def _normalize_extracted_trip_details(details: dict) -> dict:
    """Patch model-friendly trip labels into weather-friendly lookup cities."""
    if not isinstance(details, dict):
        return {}

    destination = str(details.get("destination") or "").strip()
    city = str(details.get("city") or "").strip()
    alias = _WEATHER_CITY_ALIASES.get((destination, city))
    if alias:
        details = {**details, "city": alias}
    return details


def _message_text(content, max_len: int = 600) -> str:
    """Extract plain text from a message content field (str or list of blocks)."""
    if isinstance(content, str):
        return content[:max_len]
    if isinstance(content, list):
        parts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text"]
        return " ".join(parts)[:max_len]
    return ""


def extract_trip_details(messages: list) -> dict:
    """Use the fast model to extract structured trip details from conversation."""
    conversation = "\n".join(
        f"{m['role'].upper()}: {_message_text(m.get('content', ''))}"
        for m in messages
    )
    try:
        resp = llm.complete(
            model=LLM_FAST_MODEL,
            system=_EXTRACT_TRIP_SYSTEM,
            messages=[{"role": "user", "content": f"Extract trip details:\n\n{conversation}"}],
            tools=[_EXTRACT_TRIP_TOOL],
            tool_choice={"type": "function", "function": {"name": "save_trip_details"}},
            max_tokens=EXTRACTION_MAX_TOKENS,
            temperature=0,
        )
        _log_usage(LLM_FAST_MODEL, resp["usage"])
        if resp["tool_calls"]:
            return _normalize_extracted_trip_details(resp["tool_calls"][0]["input"])
    except Exception as exc:
        print(f"extract_trip_details error: {exc}")
    return {}


def extract_structured_itinerary(itinerary: str, currency: str = "EUR", issues_hint: str = "") -> dict:
    """
    Use the fast model with tool_choice to estimate the budget breakdown from an itinerary.
    Returns {"budget_breakdown": {...}} or {} on failure.
    Days are extracted separately via regex (extract_all_days) to avoid token overflow.
    """
    if not itinerary:
        return {}

    _tool = {
        "type": "function",
        "function": {
            "name": "save_itinerary",
            "description": "Persist the itinerary budget breakdown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "budget_breakdown": {
                        "type": "object",
                        "description": f"Estimated total costs in {currency} for the whole trip.",
                        "properties": {
                            "travel": {
                                "type": ["number", "null"],
                                "description": (
                                    "Intercity transport cost — flights, trains, buses, ferries, or car hire as appropriate. "
                                    "Use 0 if transport is mentioned but free/included; null only if absent from the plan."
                                ),
                            },
                            "accommodation": {"type": ["number", "null"], "description": "Total accommodation costs."},
                            "food": {"type": ["number", "null"], "description": "Total food & dining costs."},
                            "activities": {"type": ["number", "null"], "description": "Total activity & entrance-fee costs."},
                            "transport": {"type": ["number", "null"], "description": "Local transport costs within the destination (taxis, metro, auto-rickshaw, etc.)."},
                            "total_estimated": {"type": ["number", "null"], "description": "Sum of all estimated costs."},
                        },
                    },
                },
                "required": ["budget_breakdown"],
            },
        },
    }

    try:
        resp = llm.complete(
            model=LLM_FAST_MODEL,
            system=(
                f"You are a travel cost estimator. "
                f"From the itinerary below, estimate the total trip costs in {currency}. "
                f"Use any prices mentioned as anchors and estimate any missing categories "
                f"based on the destination, accommodation type, and activities described. "
                f"Every numeric field must be a positive number — never null or zero unless the trip genuinely has no cost in that category."
                + (f" Previous extraction was incomplete: {issues_hint}. Fix these gaps." if issues_hint else "")
            ),
            messages=[{"role": "user", "content": itinerary[:12000]}],
            tools=[_tool],
            tool_choice={"type": "function", "function": {"name": "save_itinerary"}},
            max_tokens=512,
            temperature=0,
        )
        _log_usage(LLM_FAST_MODEL, resp["usage"])
        if resp["tool_calls"]:
            return resp["tool_calls"][0]["input"]
    except Exception as exc:
        print(f"extract_structured_itinerary error: {exc}")
    return {}


def extract_itinerary(messages: list) -> str:
    """Pull the full itinerary text from saved conversation history."""
    heading_re = re.compile(r'(?i)(?:^|\n)[ \t]*(?:#{1,3}[ \t]*[^\w\n]*[ \t]*)?\*{0,2}day[ \t]+\d+')

    def _is_real_itinerary(content: str) -> bool:
        return len(heading_re.findall(content)) >= 2

    candidates = [m for m in reversed(messages) if m["role"] == "assistant"]

    for m in candidates:
        if _is_real_itinerary(m["content"]):
            return m["content"]

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
    heading_pattern = re.compile(
        r'(?im)^([ \t]*(?:#{1,3}[ \t]*[^\w\n]*[ \t]*)?\*{0,2}(?:DAY|Day)[ \t]+(\d+)(?:-\d+)?(?:\*{0,2})?(?:\s*\([^)]*\))?[ \t]*(?:[-—–:][^\n]*)?)$'
    )
    matches = list(heading_pattern.finditer(itinerary))
    if not matches:
        return []

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
    """Given saved trip dates, calculate which day of the trip today is."""
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


def run_agentic_loop(
    messages: list,
    system: str | list,
    on_tool_call=None,
    collected: dict | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
):
    """
    Core agentic loop — handles tool use automatically.
    Yields text chunks as they stream from the LLM.
    """
    _model = model or LLM_MODEL
    _max_tokens = max_tokens or PLANNING_MAX_TOKENS
    current_messages = list(messages)
    iteration = 0

    while True:
        iteration += 1
        if iteration > 1:
            print(f"🔄 Agentic loop iteration {iteration}")
        tool_calls = []
        finish_reason = None

        for event_type, data in llm.stream(
            _model, current_messages, system=system, tools=TOOL_DEFINITIONS, max_tokens=_max_tokens
        ):
            if event_type == "text":
                yield data
            elif event_type == "tool_use":
                tool_calls.append(data)
            elif event_type == "usage":
                _log_usage(_model, data)
            elif event_type == "finish_reason":
                finish_reason = data

        if finish_reason == "length":
            # Output hit max_tokens — flag it so the caller can skip repair
            # (a regenerate would truncate at the same ceiling).
            print(f"⚠️  Generation truncated at max_tokens={_max_tokens}")
            if collected is not None:
                collected["_truncated"] = True

        if not tool_calls:
            return

        # Append assistant turn with tool calls in OpenAI format
        current_messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["input"])},
                }
                for tc in tool_calls
            ],
        })

        # Notify caller and log before firing concurrent requests
        for tc in tool_calls:
            print(f"🔧 Marco is using tool: {tc['name']} with {tc['input']}")
            if on_tool_call is not None:
                on_tool_call(tc["name"], tc["input"])

        # Execute all tools concurrently — each is a blocking HTTP call
        _lock = threading.Lock()

        def _run(tc):
            if collected is None:
                return tc["id"], execute_tool(tc["name"], tc["input"], collected=collected)
            return tc["id"], execute_tool(tc["name"], tc["input"], collected=collected, _lock=_lock)

        results: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=len(tool_calls)) as pool:
            for tool_id, result in pool.map(_run, tool_calls):
                results[tool_id] = result

        for tc in tool_calls:
            current_messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": results[tc["id"]],
            })


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

            itinerary = extract_itinerary(trip_data.get("messages", []))
            today_plan = extract_day_section(itinerary, day_number)

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

    system = SYSTEM_PROMPT + dynamic_context

    if companion_mode:
        yield from run_agentic_loop(
            messages, system,
            on_tool_call=on_tool_call,
            collected=collected,
            model=LLM_FAST_MODEL,
            max_tokens=COMPANION_MAX_TOKENS,
        )
    else:
        from backend.agents.orchestrator import orchestrate
        yield from orchestrate(messages, system, trip_data, on_tool_call, collected)


def generate_checklist(destination: str, passport_country: str, start_date: str) -> list[dict]:
    """Use the fast model to generate a pre-trip checklist."""
    _PRIORITY_MAP = {"high": "high", "normal": "normal", "low": "low",
                     "medium": "normal", "moderate": "normal", "critical": "high"}

    try:
        resp = llm.complete(
            model=LLM_FAST_MODEL,
            system=_CHECKLIST_SYSTEM,
            messages=[{"role": "user", "content": (
                f"Generate a pre-trip checklist for:\n\n"
                f"Destination: {destination}\n"
                f"Passport / citizenship country: {passport_country or 'not specified'}\n"
                f"Departure date: {start_date or 'soon'}"
            )}],
            tools=[_CHECKLIST_TOOL],
            tool_choice={"type": "function", "function": {"name": "save_checklist"}},
            max_tokens=1024,
            temperature=0,
        )
        _log_usage(LLM_FAST_MODEL, resp["usage"])
        items = resp["tool_calls"][0]["input"]["items"] if resp["tool_calls"] else []
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
        fallback = [{"category": "insurance", "item": "Purchase travel insurance", "priority": "high"}]
        if passport_country and destination:
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
    """Use the fast model to extract travel preference signals from a post-trip debrief."""
    if not debrief_text:
        return []
    try:
        resp = llm.complete(
            model=LLM_FAST_MODEL,
            system=_PREFERENCES_SYSTEM,
            messages=[{"role": "user", "content": debrief_text}],
            tools=[_PREFERENCES_TOOL],
            tool_choice={"type": "function", "function": {"name": "save_preferences"}},
            max_tokens=256,
            temperature=0,
        )
        _log_usage(LLM_FAST_MODEL, resp["usage"])
        result = resp["tool_calls"][0]["input"].get("preferences", []) if resp["tool_calls"] else []
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
