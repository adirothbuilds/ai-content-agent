from __future__ import annotations

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import build_agno_agent, run_agent
from ai_content_agent.llm import LlmTask
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
    agent = build_agno_agent(
        task=LlmTask.WRITER,
        instructions=list(WRITER_AGENT_PROMPT.instructions),
        response_model=WriterDraft,
    )
    result = run_agent(
        agent,
        build_writer_agent_prompt(idea=idea, context_documents=context_documents),
    )
    output = result.content.model_dump()
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
