import math
from collections.abc import Mapping, Sequence
from typing import Any

from ai_content_agent.embeddings import build_embedding_vector
from ai_content_agent.repositories.retrieval import MongoRetrievalRepository
from ai_content_agent.settings import get_settings


DEFAULT_RETRIEVAL_COLLECTIONS = (
    "journal_entries",
    "github_activity",
    "draft_history",
    "post_history",
)

_retrieval_repository = None


def retrieve_documents(
    *,
    query: str,
    collections: Sequence[str] | None = None,
    metadata_filters: Mapping[str, Any] | None = None,
    top_k: int | None = None,
) -> list[dict[str, object]]:
    settings = get_settings()
    target_collections = tuple(collections or DEFAULT_RETRIEVAL_COLLECTIONS)
    repository = get_retrieval_repository()
    raw_documents = repository.fetch_documents(
        collections=target_collections,
        metadata_filters=metadata_filters,
    )

    query_vector = build_embedding_vector(query)
    scored_documents = []
    for document in raw_documents:
        similarity = _cosine_similarity(
            query_vector,
            _extract_embedding_vector(document),
        )
        scored_documents.append((similarity, document))

    scored_documents.sort(key=lambda item: item[0], reverse=True)
    limited_documents = scored_documents[: (top_k or settings.retrieval_top_k)]

    return [
        {
            "document_id": document.get("id"),
            "document_type": document.get("document_type"),
            "collection": _infer_collection_name(document),
            "content": document.get("content", ""),
            "score": round(score, 6),
            "metadata": dict(document.get("metadata", {})),
            "provenance": dict(document.get("provenance", {})),
        }
        for score, document in limited_documents
    ]


def get_retrieval_repository():
    global _retrieval_repository
    if _retrieval_repository is None:
        _retrieval_repository = MongoRetrievalRepository(get_settings())
    return _retrieval_repository


def set_retrieval_repository(repository) -> None:
    global _retrieval_repository
    _retrieval_repository = repository


def _extract_embedding_vector(document: Mapping[str, Any]) -> list[float]:
    embedding = document.get("embedding") or {}
    vector = embedding.get("vector")
    if isinstance(vector, list):
        return [float(value) for value in vector]
    return []


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return numerator / (left_norm * right_norm)


def _infer_collection_name(document: Mapping[str, Any]) -> str:
    document_type = document.get("document_type")
    if document_type == "journal_entry":
        return "journal_entries"
    if document_type == "github_activity":
        return "github_activity"
    if document_type == "draft_history":
        return "draft_history"
    if document_type == "post_history":
        return "post_history"
    return "unknown"
