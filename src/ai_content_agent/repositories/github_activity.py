from collections.abc import Mapping, Sequence
from typing import Any

from ai_content_agent.settings import Settings


class MongoGitHubActivityRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def save_many(self, documents: Sequence[Mapping[str, Any]]) -> None:
        if not documents:
            return

        try:
            from pymongo import MongoClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pymongo is required to persist GitHub activity to MongoDB."
            ) from exc

        client = MongoClient(self._settings.mongodb_uri)
        try:
            database = client[self._settings.mongodb_database]
            database["github_activity"].insert_many([dict(document) for document in documents])
        finally:
            client.close()
