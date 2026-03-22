from __future__ import annotations

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import build_agno_agent, run_agent
from ai_content_agent.llm import LlmTask
from ai_content_agent.prompts import REMIX_AGENT_PROMPT, build_remix_agent_prompt


class RemixDraft(BaseModel):
    draft: str = Field(min_length=1)
    change_summary: str = Field(min_length=1)


def generate_remix_draft(*, draft: str, feedback: str) -> dict[str, object]:
    agent = build_agno_agent(
        task=LlmTask.REMIX,
        instructions=list(REMIX_AGENT_PROMPT.instructions),
        response_model=RemixDraft,
    )
    result = run_agent(agent, build_remix_agent_prompt(draft=draft, feedback=feedback))
    output = result.content.model_dump()
    output["prompt_version"] = REMIX_AGENT_PROMPT.version
    return output
