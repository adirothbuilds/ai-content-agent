from collections.abc import Mapping
from typing import Any

from ai_content_agent.settings import Settings


class MongoCheckpointRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_last_published_checkpoint(self) -> dict[str, Any] | None:
        try:
            from pymongo import DESCENDING, MongoClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pymongo is required to read checkpoint state from MongoDB."
            ) from exc

        client = MongoClient(self._settings.mongodb_uri)
        try:
            database = client[self._settings.mongodb_database]
            return database["post_checkpoints"].find_one(
                {"checkpoint_type": "last_published_post"},
                sort=[("published_at", DESCENDING)],
            )
        finally:
            client.close()

    def save_last_published_checkpoint(self, document: Mapping[str, Any]) -> None:
        try:
            from pymongo import MongoClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pymongo is required to persist checkpoint state to MongoDB."
            ) from exc

        client = MongoClient(self._settings.mongodb_uri)
        try:
            database = client[self._settings.mongodb_database]
            database["post_checkpoints"].replace_one(
                {"checkpoint_type": "last_published_post"},
                dict(document),
                upsert=True,
            )
        finally:
            client.close()
