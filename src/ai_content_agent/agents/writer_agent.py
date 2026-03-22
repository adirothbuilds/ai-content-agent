from __future__ import annotations

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import build_agno_agent, run_agent
from ai_content_agent.llm import LlmTask


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
        instructions=[
            "Write a LinkedIn draft grounded in the selected idea and source context.",
            "Preserve factual accuracy and cite only provided source document IDs.",
            "Do not invent achievements, metrics, or implementation details.",
        ],
        response_model=WriterDraft,
    )
    result = run_agent(agent, _build_prompt(idea, context_documents))
    output = result.content.model_dump()
    output["source_document_ids"] = _validated_source_document_ids(
        output["source_document_ids"],
        context_documents,
    )
    if not output["source_document_ids"]:
        raise ValueError("Writer Agent returned no valid source document IDs.")
    return output


def _build_prompt(
    idea: dict[str, object],
    context_documents: list[dict[str, object]],
) -> str:
    context_lines = []
    for document in context_documents:
        context_lines.append(
            "\n".join(
                [
                    f"ID: {document['document_id']}",
                    f"Type: {document['document_type']}",
                    f"Content: {document['content']}",
                ]
            )
        )
    return "\n\n".join(
        [
            f"Selected idea title: {idea['title']}",
            f"Angle: {idea['angle']}",
            f"Summary: {idea['summary']}",
            f"Preferred source IDs: {', '.join(idea['source_document_ids'])}",
            "Context documents:",
            "\n\n".join(context_lines),
        ]
    )


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
