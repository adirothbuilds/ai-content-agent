from fastapi import APIRouter

from ai_content_agent.services.github_sync import sync_github_activity


router = APIRouter(prefix="/github", tags=["github"])


@router.post("/sync", summary="Sync GitHub activity")
async def github_sync() -> dict[str, object]:
    return {"ok": True, "sync": sync_github_activity()}
