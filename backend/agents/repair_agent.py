"""
Repair agent — streams a corrected itinerary reusing the original PlannerInput.

Does NOT re-run extraction or research. The evidence from the first planning
pass is reused directly. Called at most once per request — no retry loop.
"""

from __future__ import annotations

from backend.agents.models import CriticResult, PlannerInput
from backend.agents.planner_agent import plan


def repair(
    planner_input: PlannerInput,
    original_itinerary: str,
    critic_result: CriticResult,
    system_base: str,
    on_tool_call=None,
    collected: dict | None = None,
):
    """
    Stream a corrected itinerary.

    Appends the original itinerary and the critic's targeted repair instruction
    to the conversation, then re-runs the planner with the same evidence.

    Args:
        planner_input:      PlannerInput from the first planning pass.
        original_itinerary: Full text of the itinerary that failed eval.
        critic_result:      Structured evaluation with issues list.
        system_base:        SYSTEM_PROMPT + dynamic context from chat().
        on_tool_call:       Callback(tool_name, tool_input) for SSE events.
        collected:          Mutable dict; additional hotel suggestions merged in.
    """
    instruction = critic_result.repair_instruction()
    if not instruction:
        return

    repair_messages = planner_input.messages + [
        {"role": "assistant", "content": original_itinerary},
        {"role": "user", "content": instruction},
    ]

    repair_input = PlannerInput(
        extraction=planner_input.extraction,
        evidence=planner_input.evidence,
        messages=repair_messages,
    )

    print(f"🔧 Repair: {critic_result.issues}")
    yield from plan(repair_input, system_base, on_tool_call=on_tool_call, collected=collected)
