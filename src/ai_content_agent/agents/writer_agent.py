from __future__ import annotations

import re

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import (
    build_agno_agent,
    coerce_response_model_output,
    run_agent,
)
from ai_content_agent.llm import LlmTask, resolve_task_config
from ai_content_agent.model_telemetry import update_model_call_record
from ai_content_agent.prompts import WRITER_AGENT_PROMPT, build_writer_agent_prompt


class WriterDraft(BaseModel):
    title: str = Field(min_length=1)
    draft: str = Field(min_length=1)
    source_document_ids: list[str] = Field(min_length=1)
    provenance_summary: str = Field(min_length=1)


def generate_writer_draft(
    *,
    idea: dict[str, object],
    context_documents: list[dict[str, object]],
) -> dict[str, object]:
    task_config = resolve_task_config(LlmTask.WRITER)
    agent = build_agno_agent(
        task=LlmTask.WRITER,
        instructions=list(WRITER_AGENT_PROMPT.instructions),
        response_model=WriterDraft,
    )
    result = run_agent(
        agent,
        build_writer_agent_prompt(idea=idea, context_documents=context_documents),
        task=LlmTask.WRITER,
        provider=task_config.provider.value,
        model=task_config.model,
        prompt_version=WRITER_AGENT_PROMPT.version,
        structured_output_expected=True,
    )
    try:
        output = coerce_response_model_output(result.content, WriterDraft).model_dump()
        if getattr(result, "record_id", None):
            update_model_call_record(
                result.record_id,
                structured_output_observed=True,
                fallback_used=False,
            )
    except TypeError:
        output = _build_writer_fallback(
            raw_content=str(result.content),
            idea=idea,
            context_documents=context_documents,
        )
        if getattr(result, "record_id", None):
            update_model_call_record(
                result.record_id,
                structured_output_observed=False,
                fallback_used=True,
            )
    output["source_document_ids"] = _validated_source_document_ids(
        output["source_document_ids"],
        context_documents,
    )
    if not output["source_document_ids"]:
        raise ValueError("Writer Agent returned no valid source document IDs.")
    output["prompt_version"] = WRITER_AGENT_PROMPT.version
    return output


def _validated_source_document_ids(
    source_document_ids: list[str],
    context_documents: list[dict[str, object]],
) -> list[str]:
    valid_ids = {
        str(document["document_id"])
        for document in context_documents
        if document.get("document_id")
    }
    return [str(value) for value in source_document_ids if str(value) in valid_ids]


def _build_writer_fallback(
    *,
    raw_content: str,
    idea: dict[str, object],
    context_documents: list[dict[str, object]],
) -> dict[str, object]:
    cleaned = raw_content.strip()
    preferred_source_ids = [
        str(value) for value in idea.get("source_document_ids", []) if str(value)
    ]
    valid_source_ids = _validated_source_document_ids(preferred_source_ids, context_documents)
    if not valid_source_ids:
        valid_source_ids = _validated_source_document_ids(
            [str(document.get("document_id")) for document in context_documents],
            context_documents,
        )

    title = _extract_title(cleaned) or str(idea.get("title", "Generated draft")).strip()
    return {
        "title": title,
        "draft": cleaned,
        "source_document_ids": valid_source_ids,
        "provenance_summary": "Derived from a plain-text writer response using the selected grounded source context.",
    }


def _extract_title(content: str) -> str | None:
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = re.sub(r"^[#*\-\s]+", "", stripped).strip().strip("*#- ").strip()
        if stripped:
            return stripped[:120]
    return None
