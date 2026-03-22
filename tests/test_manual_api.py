from pathlib import Path

from fastapi.testclient import TestClient

from ai_content_agent.app import create_app
from ai_content_agent.services.journal_entries import set_journal_entry_repository
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
}


class FakeJournalEntryRepository:
    def __init__(self) -> None:
        self.documents: list[dict[str, object]] = []

    def save(self, document) -> None:
        self.documents.append(dict(document))


def _set_environment(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()


def test_manual_journal_and_github_endpoints(monkeypatch) -> None:
    _set_environment(monkeypatch)
    repository = FakeJournalEntryRepository()
    set_journal_entry_repository(repository)
    monkeypatch.setattr(
        "ai_content_agent.services.journal_entries.build_embedding_vector",
        lambda _: [0.1] * 8,
    )
    monkeypatch.setattr(
        "ai_content_agent.api.routes.github.sync_github_activity",
        lambda: {
            "since": "2026-03-20T10:00:00+00:00",
            "counts": {"commits": 1, "pull_requests": 0, "merged_pull_requests": 0, "issues": 0},
            "documents_saved": 1,
        },
    )

    client = TestClient(create_app())

    journal_response = client.post(
        "/journal-entries",
        json={
            "chat_id": 456,
            "user_id": 100,
            "work_summary": "Built a publish workflow.",
            "problem_solved": "The bot could not progress past idea generation.",
            "tools_used": "FastAPI, Agno, MongoDB",
            "lesson_learned": "Keep workflow state outside route handlers.",
            "outcome": "An end-to-end Telegram content loop.",
            "why_it_matters": "It makes the product testable.",
        },
    )

    assert journal_response.status_code == 200
    assert journal_response.json()["journal_entry"]["document_type"] == "journal_entry"
    assert len(repository.documents) == 1

    github_response = client.post("/github/sync")
    assert github_response.status_code == 200
    assert github_response.json()["sync"]["documents_saved"] == 1


def test_manual_generation_publish_and_history_endpoints(monkeypatch) -> None:
    _set_environment(monkeypatch)
    monkeypatch.setattr(
        "ai_content_agent.api.routes.ideas.generate_ideas_for_request",
        lambda **_: {
            "ideas": [
                {
                    "title": "Workflow state matters",
                    "angle": "Persist drafts to preserve lineage",
                    "summary": "Explain why draft and post history belong in the workflow.",
                    "source_document_ids": ["journal-1"],
                }
            ],
            "context_documents": [
                {
                    "document_id": "journal-1",
                    "document_type": "journal_entry",
                    "content": "Worked on publish flow.",
                    "score": 0.9,
                }
            ],
            "llm": {"model": "gpt-5", "metrics": {}, "prompt_version": "v1"},
            "github_sync": {"since": None, "counts": {}, "documents_saved": 0},
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.api.routes.drafts.generate_draft_for_request",
        lambda **_: {
            "writer_draft": {"id": "draft-writer-1"},
            "draft": {
                "id": "draft-seo-1",
                "payload": {
                    "title": "Workflow state matters",
                    "draft": "A polished draft.",
                    "hashtags": ["#python"],
                },
            },
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.api.routes.drafts.remix_draft_for_request",
        lambda **_: {
            "draft": {
                "id": "draft-remix-1",
                "payload": {"draft": "A remixed draft."},
            }
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.api.routes.posts.publish_draft_for_request",
        lambda **_: {
            "post": {
                "id": "post-1",
                "payload": {"title": "Workflow state matters", "draft": "A published draft."},
            },
            "checkpoint": {"checkpoint_type": "last_published_post"},
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.api.routes.posts.list_recent_post_history",
        lambda limit=5: [
            {
                "id": "post-1",
                "payload": {"title": "Workflow state matters", "draft": "A published draft."},
                "published_at": "2026-03-22T16:00:00+00:00",
            }
        ][:limit],
    )

    client = TestClient(create_app())

    ideas_response = client.post("/ideas/generate", json={"prompt": "workflow state"})
    assert ideas_response.status_code == 200
    assert len(ideas_response.json()["ideas"]) == 1

    drafts_response = client.post(
        "/drafts/generate",
        json={
            "chat_id": 456,
            "user_id": 100,
            "idea": {
                "title": "Workflow state matters",
                "angle": "Persist drafts to preserve lineage",
                "summary": "Explain why draft and post history belong in the workflow.",
                "source_document_ids": ["journal-1"],
            },
            "context_documents": [
                {
                    "document_id": "journal-1",
                    "document_type": "journal_entry",
                    "content": "Worked on publish flow.",
                }
            ],
        },
    )
    assert drafts_response.status_code == 200
    assert drafts_response.json()["draft"]["id"] == "draft-seo-1"

    remix_response = client.post(
        "/drafts/draft-seo-1/remix",
        json={"feedback": "Make it shorter."},
    )
    assert remix_response.status_code == 200
    assert remix_response.json()["draft"]["id"] == "draft-remix-1"

    publish_response = client.post("/posts/draft-remix-1/publish")
    assert publish_response.status_code == 200
    assert publish_response.json()["checkpoint"]["checkpoint_type"] == "last_published_post"

    history_response = client.get("/posts/history")
    assert history_response.status_code == 200
    assert len(history_response.json()["posts"]) == 1
