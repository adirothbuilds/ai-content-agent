from collections.abc import Mapping
from typing import Any

from ai_content_agent.settings import Settings


class MongoDraftHistoryRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def save(self, document: Mapping[str, Any]) -> None:
        try:
            from pymongo import MongoClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pymongo is required to persist draft history to MongoDB."
            ) from exc

        client = MongoClient(self._settings.mongodb_uri)
        try:
            database = client[self._settings.mongodb_database]
            database["draft_history"].insert_one(dict(document))
        finally:
            client.close()

    def get_by_id(self, draft_id: str) -> dict[str, Any] | None:
        try:
            from pymongo import MongoClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pymongo is required to load draft history from MongoDB."
            ) from exc

        client = MongoClient(self._settings.mongodb_uri)
        try:
            database = client[self._settings.mongodb_database]
            document = database["draft_history"].find_one({"id": draft_id})
            return _normalize_document(document)
        finally:
            client.close()


def _normalize_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    normalized = dict(document)
    normalized.pop("_id", None)
    return normalized
