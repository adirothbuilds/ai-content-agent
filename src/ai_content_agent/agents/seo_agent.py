from __future__ import annotations

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import build_agno_agent, run_agent
from ai_content_agent.llm import LlmTask


class SeoRevision(BaseModel):
    draft: str = Field(min_length=1)
    hashtags: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)


def generate_seo_revision(draft: str) -> dict[str, object]:
    agent = build_agno_agent(
        task=LlmTask.SEO,
        instructions=[
            "Improve LinkedIn draft visibility with formatting and relevant hashtags.",
            "Do not change the factual meaning of the draft.",
            "Keep the tone aligned with the original input.",
        ],
        response_model=SeoRevision,
    )
    result = run_agent(agent, f"Revise this draft for SEO without changing meaning:\n\n{draft}")
    return result.content.model_dump()
