from collections.abc import Mapping
from typing import Any

from ai_content_agent.settings import Settings


class MongoPostHistoryRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def save(self, document: Mapping[str, Any]) -> None:
        try:
            from pymongo import MongoClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pymongo is required to persist post history to MongoDB."
            ) from exc

        client = MongoClient(self._settings.mongodb_uri)
        try:
            database = client[self._settings.mongodb_database]
            database["post_history"].insert_one(dict(document))
        finally:
            client.close()

    def get_by_id(self, post_id: str) -> dict[str, Any] | None:
        try:
            from pymongo import MongoClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pymongo is required to load post history from MongoDB."
            ) from exc

        client = MongoClient(self._settings.mongodb_uri)
        try:
            database = client[self._settings.mongodb_database]
            document = database["post_history"].find_one({"id": post_id})
            return _normalize_document(document)
        finally:
            client.close()

    def list_recent(self, limit: int = 5) -> list[dict[str, Any]]:
        try:
            from pymongo import DESCENDING, MongoClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pymongo is required to list post history from MongoDB."
            ) from exc

        client = MongoClient(self._settings.mongodb_uri)
        try:
            database = client[self._settings.mongodb_database]
            cursor = database["post_history"].find().sort("published_at", DESCENDING).limit(limit)
            return [_normalize_document(document) for document in cursor]
        finally:
            client.close()


def _normalize_document(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if document is None:
        return None
    normalized = dict(document)
    normalized.pop("_id", None)
    return normalized
