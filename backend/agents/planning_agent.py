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
    EXTRACTION_MAX_TOKENS,
)

load_dotenv()

client = Anthropic()


def load_prompt(filename: str) -> str:
    """Load a prompt from the prompts directory."""
    prompts_dir = os.path.join(os.path.dirname(__file__), '..', 'prompts')
    filepath = os.path.join(prompts_dir, filename)
    with open(filepath, 'r') as f:
        return f.read()


SYSTEM_PROMPT = load_prompt("marco.md")


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

No markdown, no explanation. JSON object only.""",
            messages=[
                {"role": "user", "content": f"Extract trip details:\n\n{conversation}"}
            ]
        )
        raw = response.content[0].text.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except Exception:
        return {}


def extract_budget_breakdown(itinerary: str, currency: str = "EUR") -> dict:
    """
    Use Claude Haiku to extract a structured cost breakdown from the itinerary text.
    Returns a dict with estimated costs per category, or {} on failure.
    """
    if not itinerary:
        return {}

    try:
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=EXTRACTION_MAX_TOKENS,
            system=f"""Extract an estimated budget breakdown from a travel itinerary.
Return ONLY a JSON object with numeric values in {currency}:
{{
  "flights": <number or null>,
  "accommodation": <number or null>,
  "food": <number or null>,
  "activities": <number or null>,
  "transport": <number or null>,
  "total_estimated": <number or null>
}}
Use null when there is no mention of that category.
No markdown, no explanation. JSON object only.""",
            messages=[
                {"role": "user", "content": f"Extract budget breakdown:\n\n{itinerary[:3000]}"}
            ],
        )
        raw = response.content[0].text.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except Exception:
        return {}


def extract_itinerary(messages: list) -> str:
    """Pull the full itinerary text from saved conversation history."""
    return next(
        (m["content"] for m in reversed(messages)
         if m["role"] == "assistant" and "day 1" in m["content"].lower()),
        ""
    )


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
    # A real day heading line must end with either:
    #   a separator (—, -, –, :) followed by a title, OR
    #   end of line (for bare "Day N" or "**Day N**" headings).
    # This prevents matching inline commentary like "Day 1 is REST DAY..." or "Day 7 feels..."
    heading_pattern = re.compile(
        r'(?im)^([ \t]*(?:#{1,3}[ \t]*)?\*{0,2}(?:DAY|Day)[ \t]+(\d+)(?:\*{0,2})?[ \t]*(?:[-—–:][^\n]*)?)$'
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


def run_agentic_loop(messages: list, system: str, on_tool_call=None):
    """
    Core agentic loop — handles tool use automatically.
    Yields text chunks as they stream from Claude.

    Args:
        messages:     Conversation history (list of role/content dicts).
        system:       System prompt string.
        on_tool_call: Optional callable(tool_name: str, tool_input: dict) fired
                      just before each tool is executed. Use it to surface live
                      progress in a UI (e.g., update an st.empty() container).
    """

    current_messages = messages.copy()

    while True:
        with client.messages.stream(
            model=SONNET_MODEL,
            max_tokens=PLANNING_MAX_TOKENS,
            system=system,
            tools=TOOL_DEFINITIONS,
            messages=current_messages
        ) as stream:
            for text in stream.text_stream:
                yield text

            final_message = stream.get_final_message()

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
                    result = execute_tool(block.name, block.input)
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


def chat(messages: list, trip_data: dict = None, companion_mode: bool = False, on_tool_call=None):
    """Send a message to Marco and get a streaming response."""

    today = datetime.now().strftime("%A, %B %d, %Y")
    system_with_context = SYSTEM_PROMPT + f"\n\n## Current Date\nToday is {today}."

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

            # Pre-fetch weather so it's guaranteed in context.
            # city → country_code is optional, destination is the last resort.
            city = trip_data.get("city") or trip_data.get("destination", "")
            country_code = trip_data.get("country_code", "")
            weather_text = ""
            if city:
                try:
                    weather_data = get_weather_forecast(city, country_code)
                    weather_text = format_weather_for_marco(weather_data)
                except Exception:
                    pass

            system_with_context += f"""

## COMPANION MODE — ACTIVE TRIP
The user is CURRENTLY ON THIS TRIP. Today is Day {day_number} of {total_days}.
- Destination: {trip_data.get('destination')}
- Trip dates: {trip_data.get('start_date')} to {trip_data.get('end_date')}

Switch fully into companion mode: short, punchy, actionable. They're on their phone.
Lead with weather impact — what does today's forecast mean for the plan?
If weather is bad, restructure proactively. Don't just warn — give the fix.
Ask how yesterday went if it's Day 2+."""

            if today_plan:
                system_with_context += f"""

## TODAY'S ITINERARY (Day {day_number})
{today_plan}"""

            if weather_text:
                system_with_context += f"""

## CURRENT WEATHER (fetched live)
{weather_text}
Use this to adjust today's plan. Don't mention you fetched it — just act on it."""

    yield from run_agentic_loop(messages, system_with_context, on_tool_call=on_tool_call)

if __name__ == "__main__":
    test_messages = [
        {
            "role": "user",
            "content": "Hey, I want to plan a solo trip from Amsterdam to Barcelona in late May for 5 days with a budget of €800. Can you help and also check flights?"
        }
    ]
    result = "".join(chat(test_messages))
    print(result)