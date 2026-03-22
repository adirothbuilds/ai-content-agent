from collections.abc import Mapping, Sequence
from typing import Any

from ai_content_agent.settings import Settings


class MongoRetrievalRepository:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def fetch_documents(
        self,
        *,
        collections: Sequence[str],
        metadata_filters: Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            from pymongo import MongoClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "pymongo is required to retrieve documents from MongoDB."
            ) from exc

        client = MongoClient(self._settings.mongodb_uri)
        try:
            database = client[self._settings.mongodb_database]
            documents: list[dict[str, Any]] = []
            mongo_filter = _build_mongo_filter(metadata_filters or {})

            for collection_name in collections:
                documents.extend(database[collection_name].find(mongo_filter))

            return documents
        finally:
            client.close()


def _build_mongo_filter(metadata_filters: Mapping[str, Any]) -> dict[str, Any]:
    mongo_filter: dict[str, Any] = {}
    for key, value in metadata_filters.items():
        if "." in key:
            mongo_filter[key] = value
        else:
            mongo_filter[f"metadata.{key}"] = value
    return mongo_filter
