from __future__ import annotations

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import build_agno_agent, run_agent
from ai_content_agent.llm import LlmTask


class RemixDraft(BaseModel):
    draft: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)


def generate_remix_draft(*, draft: str, feedback: str) -> dict[str, object]:
    agent = build_agno_agent(
        task=LlmTask.REMIX,
        instructions=[
            "Revise the draft using explicit user feedback.",
            "Preserve the factual content unless the feedback directly asks for a removal or reframing.",
            "Keep the revised output coherent and publication-ready.",
        ],
        response_model=RemixDraft,
    )
    result = run_agent(
        agent,
        "\n\n".join(
            [
                "Original draft:",
                draft,
                "User feedback:",
                feedback,
            ]
        ),
    )
    return result.content.model_dump()
