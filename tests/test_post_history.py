from pathlib import Path

from ai_content_agent.services.post_history import (
    evaluate_draft_candidate,
    evaluate_idea_candidates,
)
from ai_content_agent.services.retrieval import set_retrieval_repository
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
    "RETRIEVAL_TOP_K": "3",
    "POST_HISTORY_SIMILARITY_THRESHOLD": "0.8",
}


class FakeRetrievalRepository:
    def __init__(self, documents: list[dict[str, object]]) -> None:
        self.documents = documents

    def fetch_documents(self, *, collections, metadata_filters=None):
        assert tuple(collections) == ("post_history",)
        return list(self.documents)


def test_evaluate_idea_candidates_flags_similar_post_history(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    set_retrieval_repository(
        FakeRetrievalRepository(
            [
                {
                    "id": "post-1",
                    "document_type": "post_history",
                    "content": "How I built a Telegram webhook flow",
                    "metadata": {"post_kind": "published"},
                    "provenance": {"source": "linkedin"},
                    "embedding": {"vector": [1.0, 0.0, 0.0]},
                },
                {
                    "id": "post-2",
                    "document_type": "post_history",
                    "content": "Lessons from GitHub activity sync",
                    "metadata": {"post_kind": "published"},
                    "provenance": {"source": "linkedin"},
                    "embedding": {"vector": [0.0, 1.0, 0.0]},
                },
            ]
        )
    )
    monkeypatch.setattr(
        "ai_content_agent.services.retrieval.build_embedding_vector",
        lambda query: [1.0, 0.0, 0.0] if "webhook" in query else [0.0, 0.0, 1.0],
    )

    evaluations = evaluate_idea_candidates(
        [
            "A new webhook implementation story",
            "A note about team process",
        ]
    )

    assert evaluations[0]["has_similar_history"] is True
    assert evaluations[0]["matches"][0]["document_id"] == "post-1"
    assert evaluations[1]["has_similar_history"] is False


def test_evaluate_draft_candidate_uses_threshold(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("POST_HISTORY_SIMILARITY_THRESHOLD", "0.95")
    reset_settings_cache()

    set_retrieval_repository(
        FakeRetrievalRepository(
            [
                {
                    "id": "post-1",
                    "document_type": "post_history",
                    "content": "How I built a Telegram webhook flow",
                    "metadata": {"post_kind": "published"},
                    "provenance": {"source": "linkedin"},
                    "embedding": {"vector": [0.7, 0.7, 0.0]},
                }
            ]
        )
    )
    monkeypatch.setattr(
        "ai_content_agent.services.retrieval.build_embedding_vector",
        lambda _: [1.0, 0.0, 0.0],
    )

    evaluation = evaluate_draft_candidate("Webhook draft")

    assert evaluation["has_similar_history"] is False
    assert evaluation["matches"] == []
