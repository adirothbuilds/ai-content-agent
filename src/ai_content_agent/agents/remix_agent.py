from __future__ import annotations

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import (
    build_agno_agent,
    coerce_response_model_output,
    run_agent,
)
from ai_content_agent.llm import LlmTask
from ai_content_agent.model_telemetry import update_model_call_record
from ai_content_agent.prompts import REMIX_AGENT_PROMPT, build_remix_agent_prompt


class RemixDraft(BaseModel):
    draft: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)


def generate_remix_draft(*, draft: str, feedback: str) -> dict[str, object]:
    from ai_content_agent.llm import resolve_task_config

    task_config = resolve_task_config(LlmTask.REMIX)
    agent = build_agno_agent(
        task=LlmTask.REMIX,
        instructions=list(REMIX_AGENT_PROMPT.instructions),
        response_model=RemixDraft,
    )
    result = run_agent(
        agent,
        build_remix_agent_prompt(draft=draft, feedback=feedback),
        task=LlmTask.REMIX,
        provider=task_config.provider.value,
        model=task_config.model,
        prompt_version=REMIX_AGENT_PROMPT.version,
        structured_output_expected=True,
    )
    try:
        output = coerce_response_model_output(result.content, RemixDraft).model_dump()
        if getattr(result, "record_id", None):
            update_model_call_record(
                result.record_id,
                structured_output_observed=True,
                fallback_used=False,
            )
    except TypeError:
        output = _build_remix_fallback(str(result.content), feedback)
        if getattr(result, "record_id", None):
            update_model_call_record(
                result.record_id,
                structured_output_observed=False,
                fallback_used=True,
            )
    output["prompt_version"] = REMIX_AGENT_PROMPT.version
    return output


def _build_remix_fallback(raw_content: str, feedback: str) -> dict[str, object]:
    cleaned = raw_content.strip()
    return {
        "draft": cleaned,
        "change_summary": f"Derived from a plain-text remix response using the feedback: {feedback}",
    }
