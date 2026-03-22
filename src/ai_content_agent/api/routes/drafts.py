from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ai_content_agent.services.content_workflow import (
    generate_draft_for_request,
    remix_draft_for_request,
)


router = APIRouter(prefix="/drafts", tags=["drafts"])


class DraftGenerationRequest(BaseModel):
    chat_id: int | None = None
    user_id: int | None = None
    idea: dict[str, object]
    context_documents: list[dict[str, object]] = Field(default_factory=list)


class DraftRemixRequest(BaseModel):
    feedback: str = Field(min_length=1)


@router.post("/generate", summary="Generate a draft from a selected idea")
async def generate_draft(payload: DraftGenerationRequest) -> dict[str, object]:
    result = generate_draft_for_request(
        chat_id=payload.chat_id,
        user_id=payload.user_id,
        idea=payload.idea,
        context_documents=payload.context_documents,
    )
    return {"ok": True, **result}


@router.post("/{draft_id}/remix", summary="Remix an existing draft")
async def remix_draft(draft_id: str, payload: DraftRemixRequest) -> dict[str, object]:
    try:
        result = remix_draft_for_request(draft_id=draft_id, feedback=payload.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"ok": True, **result}
