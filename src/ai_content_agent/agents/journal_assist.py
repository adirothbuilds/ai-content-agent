from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import build_agno_agent, run_agent
from ai_content_agent.llm import LlmTask
from ai_content_agent.prompts import (
    JOURNAL_ASSIST_PROMPT,
    build_journal_assist_prompt,
)

if TYPE_CHECKING:
    from ai_content_agent.journal_sessions import JournalSession


class JournalAssistDraft(BaseModel):
    work_summary: str = Field(min_length=1)
    problem_solved: str = Field(min_length=1)
    tools_used: str = Field(min_length=1)
    lesson_learned: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    gaps: list[str] = Field(default_factory=list)


def generate_journal_assist_draft(session: JournalSession) -> JournalAssistDraft:
    agent = build_agno_agent(
        task=LlmTask.JOURNAL_ASSIST,
        instructions=list(JOURNAL_ASSIST_PROMPT.instructions),
        response_model=JournalAssistDraft,
    )
    prompt = build_journal_assist_prompt(session)
    result = run_agent(agent, prompt)
    return result.content
