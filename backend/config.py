"""
Central configuration for Marco.
Update model names here when upgrading — do not hardcode them in other files.
"""

import os

# ── LLM Provider ──────────────────────────────────────────────────────────────
# LiteLLM model strings. Use "provider/model-name" format.
# Examples:
#   anthropic/claude-sonnet-4-6          → direct Anthropic API
#   deepseek/deepseek-chat               → direct DeepSeek API
#   deepseek/deepseek-chat + LLM_BASE_URL → via a gateway (e.g. Vercel AI)
#
# To use Vercel AI Gateway:
#   LLM_MODEL=deepseek/deepseek-chat
#   LLM_BASE_URL=https://ai-gateway.vercel.sh/v1
#   LLM_API_KEY=<your Vercel AI Gateway token>
LLM_MODEL      = os.getenv("LLM_MODEL",      "anthropic/claude-sonnet-4-6")
LLM_FAST_MODEL = os.getenv("LLM_FAST_MODEL", "anthropic/claude-haiku-4-5-20251001")
LLM_BASE_URL   = os.getenv("LLM_BASE_URL")   # custom gateway endpoint (optional)
LLM_API_KEY    = os.getenv("LLM_API_KEY")    # overrides provider-specific key (optional)

# ── Token limits ──────────────────────────────────────────────────────────────
PLANNING_MAX_TOKENS = 4096
COMPANION_MAX_TOKENS = 1024   # companion replies are short; fast model is enough
EXTRACTION_MAX_TOKENS = 256

# ── Tool defaults ─────────────────────────────────────────────────────────────
MAX_SEARCH_RESULTS = 5
DEFAULT_CURRENCY = "EUR"

# ── HTTP ──────────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT_SECONDS = 10
