"""
Provider-agnostic LLM client for Marco.

Wraps LiteLLM so the rest of the codebase never imports a provider SDK directly.
Switching providers = changing env vars only, no code changes needed.

Configuration (set in .env):
  LLM_MODEL      — LiteLLM model string, e.g. "anthropic/claude-sonnet-4-6"
  LLM_FAST_MODEL — Model for quick extraction tasks (defaults to LLM_MODEL)
  LLM_BASE_URL   — Custom gateway URL, e.g. "https://ai-gateway.vercel.sh/v1"
  LLM_API_KEY    — API key for the gateway (or provider-specific keys like
                   ANTHROPIC_API_KEY / DEEPSEEK_API_KEY also work)

Example — DeepSeek via Vercel AI Gateway:
  LLM_MODEL=deepseek/deepseek-chat
  LLM_FAST_MODEL=deepseek/deepseek-chat
  LLM_BASE_URL=https://ai-gateway.vercel.sh/v1
  LLM_API_KEY=<your Vercel AI Gateway token>
"""

import json
import litellm
from backend.config import (
    LLM_BASE_URL,
    LLM_API_KEY,
    LLM_COMPLETE_TIMEOUT_SECONDS,
    LLM_STREAM_TIMEOUT_SECONDS,
    LLM_RETRIES,
)

litellm.suppress_debug_info = True
# Drop request params a provider doesn't support (e.g. stream_options,
# cache_control) instead of erroring — keeps the wrapper provider-agnostic.
litellm.drop_params = True


def _base_kwargs() -> dict:
    """Build kwargs shared across every LiteLLM call."""
    kw: dict = {}
    if LLM_BASE_URL:
        kw["api_base"] = LLM_BASE_URL
        # Treat any custom endpoint as OpenAI-compatible so LiteLLM doesn't
        # try to route the call through the provider inferred from the model prefix.
        kw["custom_llm_provider"] = "openai"
    if LLM_API_KEY:
        kw["api_key"] = LLM_API_KEY
    return kw


_BASE_KW = _base_kwargs()


def _supports_prompt_cache(model: str) -> bool:
    """Anthropic prompt caching only works on the direct Anthropic route."""
    return model.startswith("anthropic/") and not LLM_BASE_URL


def _build_messages(model: str, system: str | list | None, messages: list) -> list:
    """Prepend system prompt as a system-role message (OpenAI format).

    On the direct Anthropic route the system prompt is sent as a content block
    with a cache_control breakpoint, so repeated calls with the same system
    prefix (agentic loop iterations, repair pass, multi-turn chat) hit the
    prompt cache instead of paying full input price every time.
    """
    result = []
    if system:
        if isinstance(system, list):
            # Flatten Anthropic-style blocks into one text body
            text = "\n\n".join(
                b["text"] for b in system if isinstance(b, dict) and "text" in b
            )
        else:
            text = system
        if _supports_prompt_cache(model):
            result.append({
                "role": "system",
                "content": [{
                    "type": "text",
                    "text": text,
                    "cache_control": {"type": "ephemeral"},
                }],
            })
        else:
            result.append({"role": "system", "content": text})
    result.extend(messages)
    return result


def _usage_dict(usage) -> dict:
    """Normalise a LiteLLM usage object, including Anthropic cache counters."""
    details = getattr(usage, "prompt_tokens_details", None)
    cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
    return {
        "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "cache_read_tokens": (getattr(usage, "cache_read_input_tokens", 0) or 0) or cached,
        "cache_creation_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
    }


def stream(
    model: str,
    messages: list,
    system: str | list | None = None,
    tools: list | None = None,
    max_tokens: int = 4096,
    temperature: float | None = None,
):
    """
    Stream an LLM completion.

    Yields tuples:
        ("text",     str)                                  — text delta
        ("tool_use", {"id": str, "name": str, "input": dict}) — completed tool call
        ("usage",    {"input_tokens": int, "output_tokens": int, ...})
        ("finish_reason", str)  — why generation stopped ("stop", "length", "tool_calls")
    """
    base = f" via {LLM_BASE_URL}" if LLM_BASE_URL else ""
    print(f"🤖 LLM stream: {model}{base}")
    msgs = _build_messages(model, system, messages)

    kw = {**_BASE_KW}
    if temperature is not None:
        kw["temperature"] = temperature

    resp = litellm.completion(
        model=model,
        messages=msgs,
        tools=tools or None,
        max_tokens=max_tokens,
        stream=True,
        stream_options={"include_usage": True},
        timeout=LLM_STREAM_TIMEOUT_SECONDS,
        **kw,
    )

    tool_acc: dict[int, dict] = {}
    usage_data: dict = {}
    finish_reason: str | None = None

    for chunk in resp:
        if not chunk.choices:
            # Usage-only final chunk (stream_options include_usage)
            if getattr(chunk, "usage", None):
                usage_data = _usage_dict(chunk.usage)
            continue
        choice = chunk.choices[0]
        delta = choice.delta

        if choice.finish_reason:
            finish_reason = choice.finish_reason

        if delta.content:
            yield ("text", delta.content)

        if delta.tool_calls:
            for tc in delta.tool_calls:
                idx = tc.index
                if idx not in tool_acc:
                    tool_acc[idx] = {"id": "", "name": "", "arguments": ""}
                if tc.id:
                    tool_acc[idx]["id"] = tc.id
                if tc.function and tc.function.name:
                    tool_acc[idx]["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    tool_acc[idx]["arguments"] += tc.function.arguments

        # Some providers send usage on the final content chunk instead
        if getattr(chunk, "usage", None):
            usage_data = _usage_dict(chunk.usage)

    if usage_data:
        print(f"   → {usage_data['input_tokens']} in / {usage_data['output_tokens']} out tokens"
              f" (cache read {usage_data['cache_read_tokens']})")
        yield ("usage", usage_data)

    if finish_reason:
        yield ("finish_reason", finish_reason)

    # Emit fully-accumulated tool calls after the stream ends
    for idx in sorted(tool_acc):
        tc = tool_acc[idx]
        try:
            input_data = json.loads(tc["arguments"]) if tc["arguments"] else {}
        except json.JSONDecodeError:
            input_data = {}
        yield ("tool_use", {"id": tc["id"], "name": tc["name"], "input": input_data})


def complete(
    model: str,
    messages: list,
    system: str | list | None = None,
    tools: list | None = None,
    tool_choice=None,
    max_tokens: int = 256,
    temperature: float | None = None,
) -> dict:
    """
    Non-streaming completion.

    Returns:
        {
            "text": str,
            "tool_calls": [{"id": str, "name": str, "input": dict}],
            "usage": {"input_tokens": int, "output_tokens": int, ...},
        }
    """
    base = f" via {LLM_BASE_URL}" if LLM_BASE_URL else ""
    print(f"🤖 LLM complete: {model}{base}")
    msgs = _build_messages(model, system, messages)
    kw = {**_BASE_KW}
    if tools:
        kw["tools"] = tools
    if tool_choice:
        kw["tool_choice"] = tool_choice
    if temperature is not None:
        kw["temperature"] = temperature

    resp = litellm.completion(
        model=model,
        messages=msgs,
        max_tokens=max_tokens,
        timeout=LLM_COMPLETE_TIMEOUT_SECONDS,
        num_retries=LLM_RETRIES,
        **kw,
    )

    msg = resp.choices[0].message
    result: dict = {"text": msg.content or "", "tool_calls": [], "usage": {}}

    if msg.tool_calls:
        for tc in msg.tool_calls:
            try:
                input_data = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                input_data = {}
            result["tool_calls"].append({
                "id": tc.id,
                "name": tc.function.name,
                "input": input_data,
            })

    if resp.usage:
        result["usage"] = _usage_dict(resp.usage)
        u = result["usage"]
        print(f"   → {u['input_tokens']} in / {u['output_tokens']} out tokens")

    if result["tool_calls"]:
        names = ", ".join(tc["name"] for tc in result["tool_calls"])
        print(f"   → tool_choice resolved: {names}")

    return result
