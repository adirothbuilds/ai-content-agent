from fastapi import APIRouter, HTTPException, Query, status

from ai_content_agent.services.content_workflow import publish_draft_for_request
from ai_content_agent.services.post_history_records import list_recent_post_history


router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("/{draft_id}/publish", summary="Publish a finalized draft")
async def publish_post(draft_id: str) -> dict[str, object]:
    try:
        result = publish_draft_for_request(draft_id=draft_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"ok": True, **result}


@router.get("/history", summary="List recent published post history")
async def get_post_history(limit: int = Query(default=5, ge=1, le=20)) -> dict[str, object]:
    return {"ok": True, "posts": list_recent_post_history(limit=limit)}
