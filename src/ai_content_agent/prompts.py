from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ai_content_agent.journal_schema import JOURNAL_PROMPTS

if TYPE_CHECKING:
    from ai_content_agent.journal_sessions import JournalSession


@dataclass(frozen=True)
class PromptDefinition:
    key: str
    version: str
    instructions: tuple[str, ...]


JOURNAL_ASSIST_PROMPT = PromptDefinition(
    key="journal_assist",
    version="v1",
    instructions=(
        "You help refine rough engineering journal notes into a complete, factual draft.",
        "Preserve the user's meaning. Do not invent implementation facts.",
        "Fill missing fields conservatively and identify remaining uncertainty in gaps.",
        "Return every journal field with plain text values.",
    ),
)

IDEA_AGENT_PROMPT = PromptDefinition(
    key="idea_agent",
    version="v1",
    instructions=(
        "Generate distinct LinkedIn post ideas grounded in the provided source context.",
        "Return the requested number of ideas.",
        "Each idea must cite one or more provided source document IDs.",
        "Do not invent source IDs or unsupported facts.",
    ),
)

WRITER_AGENT_PROMPT = PromptDefinition(
    key="writer_agent",
    version="v1",
    instructions=(
        "Write a LinkedIn draft grounded in the selected idea and source context.",
        "Preserve factual accuracy and cite only provided source document IDs.",
        "Do not invent achievements, metrics, or implementation details.",
    ),
)

SEO_AGENT_PROMPT = PromptDefinition(
    key="seo_agent",
    version="v1",
    instructions=(
        "Improve LinkedIn draft visibility with formatting and relevant hashtags.",
        "Do not change the factual meaning of the draft.",
        "Keep the tone aligned with the original input.",
    ),
)

REMIX_AGENT_PROMPT = PromptDefinition(
    key="remix_agent",
    version="v1",
    instructions=(
        "Revise the draft using explicit user feedback.",
        "Preserve the factual content unless the feedback directly asks for a removal or reframing.",
        "Keep the revised output coherent and publication-ready.",
    ),
)


def build_journal_assist_prompt(session: JournalSession) -> str:
    lines = [
        "Complete and refine this journal entry.",
        "Existing notes:",
    ]
    for field_name, prompt in JOURNAL_PROMPTS:
        value = session.entries.get(field_name, "[missing]")
        lines.append(f"- {prompt} {value}")
    lines.append("Return a complete draft and list unresolved gaps.")
    return "\n".join(lines)


def build_idea_agent_prompt(
    *,
    user_prompt: str,
    requested_count: int,
    context_documents: list[dict[str, object]],
) -> str:
    blocks = [
        f"User prompt: {user_prompt}",
        f"Return exactly {requested_count} ideas.",
        "Context documents:",
    ]
    for document in context_documents:
        blocks.append(
            "\n".join(
                [
                    f"ID: {document['document_id']}",
                    f"Type: {document['document_type']}",
                    f"Score: {document['score']}",
                    f"Content: {document['content']}",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_writer_agent_prompt(
    *,
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


def build_seo_agent_prompt(draft: str) -> str:
    return f"Revise this draft for SEO without changing meaning:\n\n{draft}"


def build_remix_agent_prompt(*, draft: str, feedback: str) -> str:
    return "\n\n".join(
        [
            "Original draft:",
            draft,
            "User feedback:",
            feedback,
        ]
    )
