from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ai_content_agent.embeddings import build_embedding_vector
from ai_content_agent.prompts import REMIX_AGENT_PROMPT, SEO_AGENT_PROMPT, WRITER_AGENT_PROMPT
from ai_content_agent.repositories.draft_history import MongoDraftHistoryRepository
from ai_content_agent.settings import get_settings


_draft_history_repository = None


def persist_draft_history_document(
    *,
    chat_id: int | None,
    user_id: int | None,
    idea: dict[str, object],
    draft_payload: dict[str, object],
    workflow_stage: str,
    parent_draft_id: str | None = None,
) -> dict[str, object]:
    document = build_draft_history_document(
        chat_id=chat_id,
        user_id=user_id,
        idea=idea,
        draft_payload=draft_payload,
        workflow_stage=workflow_stage,
        parent_draft_id=parent_draft_id,
    )
    get_draft_history_repository().save(document)
    return document


def get_draft_history_repository():
    global _draft_history_repository
    if _draft_history_repository is None:
        _draft_history_repository = MongoDraftHistoryRepository(get_settings())
    return _draft_history_repository


def set_draft_history_repository(repository) -> None:
    global _draft_history_repository
    _draft_history_repository = repository


def build_draft_history_document(
    *,
    chat_id: int | None,
    user_id: int | None,
    idea: dict[str, object],
    draft_payload: dict[str, object],
    workflow_stage: str,
    parent_draft_id: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    created_at = datetime.now(UTC).isoformat()
    draft_content = str(draft_payload["draft"])
    source_document_ids = [str(value) for value in draft_payload.get("source_document_ids", [])]

    return {
        "id": str(uuid4()),
        "document_type": "draft_history",
        "content": draft_content,
        "metadata": {
            "chat_id": chat_id,
            "user_id": user_id,
            "workflow_stage": workflow_stage,
            "parent_draft_id": parent_draft_id,
            "selected_idea_title": idea["title"],
            "selected_idea_angle": idea["angle"],
            "source_document_ids": source_document_ids,
            "prompt_version": _resolve_prompt_version(workflow_stage),
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
        },
        "provenance": {
            "source": "content_workflow",
            "draft_id": parent_draft_id,
            "source_document_ids": source_document_ids,
        },
        "payload": {
            "title": draft_payload.get("title"),
            "draft": draft_content,
            "hashtags": list(draft_payload.get("hashtags", [])),
            "rationale": draft_payload.get("rationale"),
            "change_summary": draft_payload.get("change_summary"),
            "provenance_summary": draft_payload.get("provenance_summary"),
        },
        "embedding": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "vector": build_embedding_vector(draft_content),
        },
        "created_at": created_at,
        "updated_at": created_at,
    }


def _resolve_prompt_version(workflow_stage: str) -> str | None:
    if workflow_stage == "writer":
        return WRITER_AGENT_PROMPT.version
    if workflow_stage == "seo":
        return SEO_AGENT_PROMPT.version
    if workflow_stage == "remix":
        return REMIX_AGENT_PROMPT.version
    return None
