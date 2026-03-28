from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import (
    build_agno_agent,
    coerce_response_model_output,
    run_agent,
)
from ai_content_agent.llm import LlmTask, resolve_task_config
from ai_content_agent.model_telemetry import update_model_call_record
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
    task_config = resolve_task_config(LlmTask.JOURNAL_ASSIST)
    result = run_agent(
        agent,
        prompt,
        task=LlmTask.JOURNAL_ASSIST,
        provider=task_config.provider.value,
        model=task_config.model,
        prompt_version=JOURNAL_ASSIST_PROMPT.version,
        structured_output_expected=True,
    )
    draft = coerce_response_model_output(result.content, JournalAssistDraft)
    if getattr(result, "record_id", None):
        update_model_call_record(
            result.record_id,
            structured_output_observed=True,
            fallback_used=False,
        )
    return draft
