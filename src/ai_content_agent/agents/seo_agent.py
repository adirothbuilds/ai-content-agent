from __future__ import annotations

import re

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import (
    build_agno_agent,
    coerce_response_model_output,
    run_agent,
)
from ai_content_agent.llm import LlmTask
from ai_content_agent.model_telemetry import update_model_call_record
from ai_content_agent.prompts import SEO_AGENT_PROMPT, build_seo_agent_prompt


class SeoRevision(BaseModel):
    draft: str = Field(min_length=1)
    hashtags: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)


def generate_seo_revision(draft: str) -> dict[str, object]:
    from ai_content_agent.llm import resolve_task_config

    task_config = resolve_task_config(LlmTask.SEO)
    agent = build_agno_agent(
        task=LlmTask.SEO,
        instructions=list(SEO_AGENT_PROMPT.instructions),
        response_model=SeoRevision,
    )
    result = run_agent(
        agent,
        build_seo_agent_prompt(draft),
        task=LlmTask.SEO,
        provider=task_config.provider.value,
        model=task_config.model,
        prompt_version=SEO_AGENT_PROMPT.version,
        structured_output_expected=True,
    )
    try:
        output = coerce_response_model_output(result.content, SeoRevision).model_dump()
        if getattr(result, "record_id", None):
            update_model_call_record(
                result.record_id,
                structured_output_observed=True,
                fallback_used=False,
            )
    except TypeError:
        output = _build_seo_fallback(str(result.content))
        if getattr(result, "record_id", None):
            update_model_call_record(
                result.record_id,
                structured_output_observed=False,
                fallback_used=True,
            )
    output["prompt_version"] = SEO_AGENT_PROMPT.version
    return output


def _build_seo_fallback(raw_content: str) -> dict[str, object]:
    cleaned = raw_content.strip()
    hashtags = []
    seen: set[str] = set()
    for hashtag in re.findall(r"#\w+", cleaned):
        normalized = hashtag.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        hashtags.append(hashtag)

    if not hashtags:
        hashtags = ["#linkedin"]

    return {
        "draft": cleaned,
        "hashtags": hashtags,
        "rationale": "Derived from a plain-text SEO response because structured output was not returned.",
    }
