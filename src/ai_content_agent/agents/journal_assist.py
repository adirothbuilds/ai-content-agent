from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import build_agno_agent, run_agent
from ai_content_agent.journal_schema import JOURNAL_PROMPTS
from ai_content_agent.llm import LlmTask

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
        instructions=[
            "You help refine rough engineering journal notes into a complete, factual draft.",
            "Preserve the user's meaning. Do not invent implementation facts.",
            "Fill missing fields conservatively and identify remaining uncertainty in gaps.",
            "Return every journal field with plain text values.",
        ],
        response_model=JournalAssistDraft,
    )
    prompt = _build_prompt(session)
    result = run_agent(agent, prompt)
    return result.content


def _build_prompt(session: JournalSession) -> str:
    lines = [
        "Complete and refine this journal entry.",
        "Existing notes:",
    ]
    for field_name, prompt in JOURNAL_PROMPTS:
        value = session.entries.get(field_name, "[missing]")
        lines.append(f"- {prompt} {value}")
    lines.append("Return a complete draft and list unresolved gaps.")
    return "\n".join(lines)
