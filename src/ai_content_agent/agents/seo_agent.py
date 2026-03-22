from __future__ import annotations

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import build_agno_agent, run_agent
from ai_content_agent.llm import LlmTask
from ai_content_agent.prompts import SEO_AGENT_PROMPT, build_seo_agent_prompt


class SeoRevision(BaseModel):
    draft: str = Field(min_length=1)
    hashtags: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)


def generate_seo_revision(draft: str) -> dict[str, object]:
    agent = build_agno_agent(
        task=LlmTask.SEO,
        instructions=list(SEO_AGENT_PROMPT.instructions),
        response_model=SeoRevision,
    )
    result = run_agent(agent, build_seo_agent_prompt(draft))
    output = result.content.model_dump()
    output["prompt_version"] = SEO_AGENT_PROMPT.version
    return output
