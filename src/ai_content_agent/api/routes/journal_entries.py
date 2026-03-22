from fastapi import APIRouter
from pydantic import BaseModel, Field

from ai_content_agent.journal_schema import JOURNAL_PROMPTS
from ai_content_agent.journal_sessions import JournalSession
from ai_content_agent.services.journal_entries import persist_confirmed_journal_entry


router = APIRouter(prefix="/journal-entries", tags=["journal-entries"])


class JournalEntryRequest(BaseModel):
    chat_id: int
    user_id: int | None = None
    work_summary: str = Field(min_length=1)
    problem_solved: str = Field(min_length=1)
    tools_used: str = Field(min_length=1)
    lesson_learned: str = Field(min_length=1)
    outcome: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    ai_assisted: bool = False


@router.post("", summary="Persist a confirmed journal entry")
async def create_journal_entry(payload: JournalEntryRequest) -> dict[str, object]:
    session = JournalSession(
        chat_id=payload.chat_id,
        user_id=payload.user_id,
        current_step_index=len(JOURNAL_PROMPTS),
        entries={
            "work_summary": payload.work_summary,
            "problem_solved": payload.problem_solved,
            "tools_used": payload.tools_used,
            "lesson_learned": payload.lesson_learned,
            "outcome": payload.outcome,
            "why_it_matters": payload.why_it_matters,
        },
        ai_assisted=payload.ai_assisted,
        status="confirmed",
    )
    document = persist_confirmed_journal_entry(session)
    return {"ok": True, "journal_entry": document}
