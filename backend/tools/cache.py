"""
Disk-based cache for external tool calls.

Keyed on (tool_name, input_params). TTLs are conservative — tool results
don't change that often and each cache hit saves a SerpApi or OpenWeather call.
"""

import hashlib
import json
import os
import time
from pathlib import Path

CACHE_DIR = os.getenv("CACHE_DIR", "data/cache")

_TTLS = {
    "get_weather_forecast": 3_600,    # 1 hour
    "search_flights":       21_600,   # 6 hours
    "search_hotels":        21_600,   # 6 hours
    "search_places":        86_400,   # 24 hours
}


def _key(tool_name: str, params: dict) -> str:
    raw = json.dumps({tool_name: params}, sort_keys=True)
    return hashlib.md5(raw.encode()).hexdigest()


def get_cached(tool_name: str, params: dict) -> str | None:
    ttl = _TTLS.get(tool_name)
    if not ttl:
        return None
    path = Path(CACHE_DIR) / f"{_key(tool_name, params)}.json"
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text())
        if time.time() - entry["ts"] > ttl:
            path.unlink(missing_ok=True)
            return None
        return entry["result"]
    except Exception:
        return None


def set_cached(tool_name: str, params: dict, result: str) -> None:
    if tool_name not in _TTLS:
        return
    try:
        Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
        path = Path(CACHE_DIR) / f"{_key(tool_name, params)}.json"
        path.write_text(json.dumps({"ts": time.time(), "result": result}))
    except Exception:
        pass
