from fastapi import APIRouter
from pydantic import BaseModel

from ai_content_agent.services.content_workflow import generate_ideas_for_request


router = APIRouter(prefix="/ideas", tags=["ideas"])


class IdeaGenerationRequest(BaseModel):
    prompt: str | None = None


@router.post("/generate", summary="Generate grounded idea candidates")
async def generate_ideas(payload: IdeaGenerationRequest) -> dict[str, object]:
    result = generate_ideas_for_request(prompt=payload.prompt)
    return {"ok": True, **result}
