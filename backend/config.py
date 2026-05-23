"""
Central configuration for Solo Travel Agent.
Update model names here when upgrading — do not hardcode them in other files.
"""

# ── Models ────────────────────────────────────────────────────────────────────
# Main planning / companion mode (streaming)
SONNET_MODEL = "claude-sonnet-4-5-20250929"

# Quick structured extraction only — do not use for high-quality output
HAIKU_MODEL = "claude-haiku-4-5-20251001"

# ── Token limits ──────────────────────────────────────────────────────────────
PLANNING_MAX_TOKENS = 4096
EXTRACTION_MAX_TOKENS = 256

# ── Tool defaults ─────────────────────────────────────────────────────────────
MAX_SEARCH_RESULTS = 5
DEFAULT_CURRENCY = "EUR"

# ── HTTP ──────────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT_SECONDS = 10
