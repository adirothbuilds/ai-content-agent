from pathlib import Path

from ai_content_agent.services.retrieval import retrieve_documents, set_retrieval_repository
from ai_content_agent.settings import reset_settings_cache


ENVIRONMENT = {
    "APP_ENV": "test",
    "APP_HOST": "127.0.0.1",
    "APP_PORT": "8000",
    "MONGODB_URI": "mongodb://localhost:27017",
    "MONGODB_DATABASE": "ai_content_agent",
    "TELEGRAM_BOT_TOKEN": "telegram-token",
    "PUBLIC_BASE_URL": "https://example.com",
    "CLOUDFLARED_TUNNEL_TOKEN": "cloudflare-token",
    "GITHUB_TOKEN": "github-token",
    "GITHUB_USERNAME": "adiroth",
    "OPENAI_API_KEY": "openai-key",
    "GEMINI_API_KEY": "gemini-key",
    "ANTHROPIC_API_KEY": "anthropic-key",
    "IDEA_PROVIDER": "openai",
    "IDEA_MODEL": "gpt-5",
    "JOURNAL_ASSIST_PROVIDER": "openai",
    "JOURNAL_ASSIST_MODEL": "gpt-5-mini",
    "SEO_PROVIDER": "gemini",
    "SEO_MODEL": "gemini-2.5-pro",
    "WRITER_PROVIDER": "anthropic",
    "WRITER_MODEL": "claude-sonnet-4",
    "REMIX_PROVIDER": "anthropic",
    "REMIX_MODEL": "claude-sonnet-4",
    "EMBEDDING_PROVIDER": "openai",
    "EMBEDDING_MODEL": "text-embedding-3-large",
    "RETRIEVAL_TOP_K": "2",
}


class FakeRetrievalRepository:
    def __init__(self, documents: dict[str, list[dict[str, object]]]) -> None:
        self.documents = documents

    def fetch_documents(self, *, collections, metadata_filters=None):
        results = []
        filters = metadata_filters or {}

        for collection in collections:
            for document in self.documents.get(collection, []):
                if _matches_filters(document, filters):
                    results.append(document)

        return results


def test_retrieve_documents_returns_top_k_across_target_collections(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    repository = FakeRetrievalRepository(
        {
            "journal_entries": [
                {
                    "id": "journal-1",
                    "document_type": "journal_entry",
                    "content": "Worked on Telegram webhook flows",
                    "metadata": {"chat_id": 1, "status": "confirmed"},
                    "provenance": {"source": "telegram"},
                    "embedding": {"vector": [1.0, 0.0, 0.0]},
                }
            ],
            "github_activity": [
                {
                    "id": "github-1",
                    "document_type": "github_activity",
                    "content": "Commit in acme/repo\nMessage: Add webhook flow",
                    "metadata": {
                        "activity_type": "github_commit",
                        "repo_full_name": "acme/repo",
                    },
                    "provenance": {"source": "github"},
                    "embedding": {"vector": [0.9, 0.1, 0.0]},
                },
                {
                    "id": "github-2",
                    "document_type": "github_activity",
                    "content": "Issue in acme/repo\nTitle: Improve tests",
                    "metadata": {
                        "activity_type": "github_issue",
                        "repo_full_name": "acme/repo",
                    },
                    "provenance": {"source": "github"},
                    "embedding": {"vector": [0.0, 1.0, 0.0]},
                },
            ],
        }
    )
    set_retrieval_repository(repository)

    monkeypatch.setattr(
        "ai_content_agent.services.retrieval.build_embedding_vector",
        lambda _: [1.0, 0.0, 0.0],
    )

    documents = retrieve_documents(
        query="telegram webhook",
        collections=["journal_entries", "github_activity"],
    )

    assert len(documents) == 2
    assert documents[0]["document_id"] == "journal-1"
    assert documents[1]["document_id"] == "github-1"
    assert documents[0]["collection"] == "journal_entries"
    assert documents[1]["collection"] == "github_activity"


def test_retrieve_documents_applies_metadata_filters(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    repository = FakeRetrievalRepository(
        {
            "github_activity": [
                {
                    "id": "github-1",
                    "document_type": "github_activity",
                    "content": "Commit in acme/repo",
                    "metadata": {
                        "activity_type": "github_commit",
                        "repo_full_name": "acme/repo",
                    },
                    "provenance": {"source": "github"},
                    "embedding": {"vector": [0.5, 0.5, 0.0]},
                },
                {
                    "id": "github-2",
                    "document_type": "github_activity",
                    "content": "Issue in other/repo",
                    "metadata": {
                        "activity_type": "github_issue",
                        "repo_full_name": "other/repo",
                    },
                    "provenance": {"source": "github"},
                    "embedding": {"vector": [0.4, 0.6, 0.0]},
                },
            ]
        }
    )
    set_retrieval_repository(repository)

    monkeypatch.setattr(
        "ai_content_agent.services.retrieval.build_embedding_vector",
        lambda _: [1.0, 0.0, 0.0],
    )

    documents = retrieve_documents(
        query="repo activity",
        collections=["github_activity"],
        metadata_filters={"repo_full_name": "acme/repo"},
        top_k=5,
    )

    assert len(documents) == 1
    assert documents[0]["document_id"] == "github-1"
    assert documents[0]["metadata"]["repo_full_name"] == "acme/repo"


def _matches_filters(document: dict[str, object], filters: dict[str, object]) -> bool:
    metadata = document.get("metadata", {})
    provenance = document.get("provenance", {})

    for key, value in filters.items():
        if "." in key:
            prefix, suffix = key.split(".", maxsplit=1)
            if prefix == "metadata" and metadata.get(suffix) != value:
                return False
            if prefix == "provenance" and provenance.get(suffix) != value:
                return False
        elif metadata.get(key) != value:
            return False

    return True
