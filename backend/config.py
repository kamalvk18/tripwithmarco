"""
Central configuration for Marco.
Update model names here when upgrading — do not hardcode them in other files.
"""

# ── Models ────────────────────────────────────────────────────────────────────
# Main planning / companion mode (streaming)
SONNET_MODEL = "claude-sonnet-4-6"

# Quick structured extraction only — do not use for high-quality output
HAIKU_MODEL = "claude-haiku-4-5-20251001"

# ── Token limits ──────────────────────────────────────────────────────────────
PLANNING_MAX_TOKENS = 4096
COMPANION_MAX_TOKENS = 1024   # companion replies are short; Haiku is enough
EXTRACTION_MAX_TOKENS = 256

# ── Tool defaults ─────────────────────────────────────────────────────────────
MAX_SEARCH_RESULTS = 5
DEFAULT_CURRENCY = "EUR"

# ── HTTP ──────────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT_SECONDS = 10
