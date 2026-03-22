from collections.abc import Mapping
from typing import Any

from ai_content_agent.settings import Settings


class MongoJournalEntryRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def save(self, document: Mapping[str, Any]) -> None:
        try:
            from pymongo import MongoClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pymongo is required to persist journal entries to MongoDB."
            ) from exc

        client = MongoClient(self._settings.mongodb_uri)
        try:
            database = client[self._settings.mongodb_database]
            database["journal_entries"].insert_one(dict(document))
        finally:
            client.close()
