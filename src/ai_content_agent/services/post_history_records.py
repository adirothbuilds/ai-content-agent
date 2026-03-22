from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ai_content_agent.embeddings import build_embedding_vector
from ai_content_agent.repositories.post_history import MongoPostHistoryRepository
from ai_content_agent.services.checkpoints import save_last_published_checkpoint
from ai_content_agent.settings import get_settings


_post_history_repository = None


def publish_draft_history_document(
    *,
    draft_document: dict[str, object],
    chat_id: int | None,
    user_id: int | None,
) -> dict[str, object]:
    document = build_post_history_document(
        draft_document=draft_document,
        chat_id=chat_id,
        user_id=user_id,
    )
    get_post_history_repository().save(document)
    document["checkpoint"] = save_last_published_checkpoint(
        published_at=_parse_timestamp(document["published_at"]),
        post_id=str(document["id"]),
    )
    return document


def list_recent_post_history(limit: int = 5) -> list[dict[str, object]]:
    return list(get_post_history_repository().list_recent(limit=limit))


def get_post_history_repository():
    global _post_history_repository
    if _post_history_repository is None:
        _post_history_repository = MongoPostHistoryRepository(get_settings())
    return _post_history_repository


def set_post_history_repository(repository) -> None:
    global _post_history_repository
    _post_history_repository = repository


def build_post_history_document(
    *,
    draft_document: dict[str, object],
    chat_id: int | None,
    user_id: int | None,
) -> dict[str, object]:
    settings = get_settings()
    published_at = datetime.now(UTC).isoformat()
    payload = dict(draft_document.get("payload", {}))
    metadata = dict(draft_document.get("metadata", {}))
    content = str(draft_document.get("content", payload.get("draft", "")))
    source_document_ids = list(metadata.get("source_document_ids", []))

    return {
        "id": str(uuid4()),
        "document_type": "post_history",
        "content": content,
        "metadata": {
            "chat_id": chat_id,
            "user_id": user_id,
            "post_kind": "published",
            "origin_draft_id": draft_document.get("id"),
            "selected_idea_title": metadata.get("selected_idea_title"),
            "selected_idea_angle": metadata.get("selected_idea_angle"),
            "source_document_ids": source_document_ids,
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
        },
        "provenance": {
            "source": "publish_flow",
            "draft_id": draft_document.get("id"),
            "source_document_ids": source_document_ids,
        },
        "payload": payload,
        "embedding": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "vector": build_embedding_vector(content),
        },
        "published_at": published_at,
        "created_at": published_at,
        "updated_at": published_at,
    }


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(UTC)
