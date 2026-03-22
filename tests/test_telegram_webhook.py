from pathlib import Path

from fastapi.testclient import TestClient

from ai_content_agent.app import create_app
from ai_content_agent.services.draft_history import set_draft_history_repository
from ai_content_agent.services.journal_entries import set_journal_entry_repository
from ai_content_agent.services.post_history_records import set_post_history_repository
from ai_content_agent.services.telegram import content_workflow_store, journal_session_store
from ai_content_agent.settings import reset_settings_cache
from ai_content_agent.telegram import TELEGRAM_SECRET_HEADER


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


class FakeDraftHistoryRepository:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, object]] = {}

    def save(self, document) -> None:
        self.documents[str(document["id"])] = dict(document)

    def get_by_id(self, draft_id: str):
        return self.documents.get(draft_id)


class FakePostHistoryRepository:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, object]] = {}

    def save(self, document) -> None:
        self.documents[str(document["id"])] = dict(document)

    def get_by_id(self, post_id: str):
        return self.documents.get(post_id)

    def list_recent(self, limit: int = 5):
        documents = list(self.documents.values())
        documents.sort(key=lambda item: item["published_at"], reverse=True)
        return documents[:limit]


def test_telegram_webhook_parses_command(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()
    set_journal_entry_repository(FakeJournalEntryRepository())
    set_draft_history_repository(FakeDraftHistoryRepository())
    set_post_history_repository(FakePostHistoryRepository())
    journal_session_store.clear_session(123)
    content_workflow_store.clear_session(123)

    client = TestClient(create_app())
    response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 1,
            "message": {
                "message_id": 10,
                "text": "/start hello",
                "from": {"id": 99, "is_bot": False, "username": "adi"},
                "chat": {"id": 123, "type": "private"},
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "update": {
            "type": "command",
            "chat_id": 123,
            "user_id": 99,
            "command": "start",
            "text": "/start hello",
            "update_id": 1,
        },
        "dispatch": {
            "action": "unsupported_command",
            "message": "Unsupported command. Use /journal, /assist, /accept_ai, /reject_ai, /review, /save, /cancel, /ideas, /select, /draft, /remix, /publish, or /history.",
        },
    }


def test_telegram_webhook_rejects_invalid_secret(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "expected-secret")
    reset_settings_cache()
    set_journal_entry_repository(FakeJournalEntryRepository())
    set_draft_history_repository(FakeDraftHistoryRepository())
    set_post_history_repository(FakePostHistoryRepository())

    client = TestClient(create_app())
    response = client.post(
        "/webhooks/telegram",
        headers={TELEGRAM_SECRET_HEADER: "wrong-secret"},
        json={
            "update_id": 1,
            "message": {
                "message_id": 10,
                "text": "hello",
                "from": {"id": 99, "is_bot": False, "username": "adi"},
                "chat": {"id": 123, "type": "private"},
            },
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid Telegram webhook secret."}


def test_telegram_webhook_accepts_matching_secret(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "expected-secret")
    reset_settings_cache()
    set_journal_entry_repository(FakeJournalEntryRepository())
    set_draft_history_repository(FakeDraftHistoryRepository())
    set_post_history_repository(FakePostHistoryRepository())

    client = TestClient(create_app())
    response = client.post(
        "/webhooks/telegram",
        headers={TELEGRAM_SECRET_HEADER: "expected-secret"},
        json={
            "update_id": 2,
            "message": {
                "message_id": 11,
                "text": "plain text",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "update": {
            "type": "message",
            "chat_id": 456,
            "user_id": 100,
            "command": None,
            "text": "plain text",
            "update_id": 2,
        },
        "dispatch": {
            "action": "missing",
            "message": "No active journal session. Send /journal to start one.",
            "session": None,
        },
    }


def test_telegram_webhook_runs_guided_journal_session(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        "ai_content_agent.services.journal_entries.build_embedding_vector",
        lambda _: [0.1] * 12,
    )
    reset_settings_cache()
    repository = FakeJournalEntryRepository()
    set_journal_entry_repository(repository)
    set_draft_history_repository(FakeDraftHistoryRepository())
    set_post_history_repository(FakePostHistoryRepository())
    journal_session_store.clear_session(456)
    content_workflow_store.clear_session(456)

    client = TestClient(create_app())

    start_response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 10,
            "message": {
                "message_id": 20,
                "text": "/journal",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert start_response.status_code == 200
    assert start_response.json()["dispatch"]["action"] == "started"
    assert start_response.json()["dispatch"]["message"] == "What did you work on?"

    prompts = [
        "Worked on Telegram flows",
        "Users needed guided capture",
        "FastAPI and Pydantic",
        "State should stay outside the route",
        "A reviewable journal draft",
        "It improves capture quality",
    ]

    expected_next_messages = [
        "What problem did you solve?",
        "What tools or tech were involved?",
        "What lesson did you learn?",
        "What was the result or outcome?",
        "Why does it matter?",
    ]

    for index, prompt in enumerate(prompts):
        response = client.post(
            "/webhooks/telegram",
            json={
                "update_id": 11 + index,
                "message": {
                    "message_id": 21 + index,
                    "text": prompt,
                    "from": {"id": 100, "is_bot": False, "username": "adi"},
                    "chat": {"id": 456, "type": "private"},
                },
            },
        )
        assert response.status_code == 200
        if index < len(expected_next_messages):
            assert response.json()["dispatch"]["message"] == expected_next_messages[index]
        else:
            assert response.json()["dispatch"]["action"] == "review_ready"
            assert "Send /save to confirm or /cancel to discard." in response.json()["dispatch"]["message"]

    save_response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 30,
            "message": {
                "message_id": 40,
                "text": "/save",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert save_response.status_code == 200
    assert save_response.json()["dispatch"]["action"] == "saved"
    assert save_response.json()["dispatch"]["session"]["status"] == "confirmed"
    assert save_response.json()["dispatch"]["journal_entry"]["document_type"] == "journal_entry"
    assert save_response.json()["dispatch"]["journal_entry"]["metadata"]["ai_assisted"] is False
    assert len(repository.documents) == 1


def test_telegram_webhook_ai_assist_requires_confirmation(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        "ai_content_agent.services.journal_entries.build_embedding_vector",
        lambda _: [0.1] * 12,
    )
    monkeypatch.setattr(
        "ai_content_agent.journal_sessions.generate_journal_assist_draft",
        lambda session: _fake_journal_assist_draft(),
    )
    reset_settings_cache()
    repository = FakeJournalEntryRepository()
    set_journal_entry_repository(repository)
    set_draft_history_repository(FakeDraftHistoryRepository())
    set_post_history_repository(FakePostHistoryRepository())
    journal_session_store.clear_session(456)
    content_workflow_store.clear_session(456)

    client = TestClient(create_app())

    client.post(
        "/webhooks/telegram",
        json={
            "update_id": 40,
            "message": {
                "message_id": 50,
                "text": "/journal",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    client.post(
        "/webhooks/telegram",
        json={
            "update_id": 41,
            "message": {
                "message_id": 51,
                "text": "rough webhook notes",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )

    assist_response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 42,
            "message": {
                "message_id": 52,
                "text": "/assist",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert assist_response.status_code == 200
    assert assist_response.json()["dispatch"]["action"] == "ai_draft_ready"
    assert "Send /accept_ai to use this draft or /reject_ai to discard it." in assist_response.json()["dispatch"]["message"]

    blocked_save = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 43,
            "message": {
                "message_id": 53,
                "text": "/save",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert blocked_save.status_code == 200
    assert blocked_save.json()["dispatch"]["action"] == "confirmation_required"

    accept_response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 44,
            "message": {
                "message_id": 54,
                "text": "/accept_ai",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["dispatch"]["action"] == "ai_accepted"
    assert accept_response.json()["dispatch"]["session"]["status"] == "ready_for_review"

    save_response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 45,
            "message": {
                "message_id": 55,
                "text": "/save",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert save_response.status_code == 200
    assert save_response.json()["dispatch"]["action"] == "saved"
    assert save_response.json()["dispatch"]["journal_entry"]["metadata"]["ai_assisted"] is True
    assert len(repository.documents) == 1


def test_telegram_webhook_runs_idea_to_publish_flow(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        "ai_content_agent.services.draft_history.build_embedding_vector",
        lambda _: [0.2] * 8,
    )
    monkeypatch.setattr(
        "ai_content_agent.services.post_history_records.build_embedding_vector",
        lambda _: [0.3] * 8,
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.sync_github_activity",
        lambda **_: {
            "since": "2026-03-20T10:00:00+00:00",
            "counts": {"commits": 1, "pull_requests": 1, "merged_pull_requests": 0, "issues": 0},
            "documents_saved": 2,
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.generate_idea_candidates",
        lambda **_: {
            "ideas": [
                {
                    "title": "Ground the post in retrieval",
                    "angle": "Use real work artifacts",
                    "summary": "Explain how journal notes and repo activity shape the content.",
                    "source_document_ids": ["journal-1", "github-1"],
                    "has_similar_history": False,
                    "duplicate_matches": [],
                },
                {
                    "title": "Turn webhook work into content",
                    "angle": "Focus on user-facing workflow",
                    "summary": "Show how Telegram review loops reduce friction.",
                    "source_document_ids": ["journal-1"],
                    "has_similar_history": False,
                    "duplicate_matches": [],
                },
                {
                    "title": "Close the publish loop",
                    "angle": "Persist drafts and post history",
                    "summary": "Make future content less repetitive by saving the final post.",
                    "source_document_ids": ["github-1"],
                    "has_similar_history": False,
                    "duplicate_matches": [],
                },
            ],
            "context_documents": [
                {
                    "document_id": "journal-1",
                    "document_type": "journal_entry",
                    "content": "Worked on Telegram publish flow.",
                    "score": 0.9,
                },
                {
                    "document_id": "github-1",
                    "document_type": "github_activity",
                    "content": "Commit: add publish loop.",
                    "score": 0.8,
                },
            ],
            "llm": {"model": "gpt-5", "metrics": {}, "prompt_version": "v1"},
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.generate_writer_draft",
        lambda **_: {
            "title": "Turn workflow state into publishable content",
            "draft": "Here is a grounded draft.",
            "source_document_ids": ["journal-1", "github-1"],
            "provenance_summary": "Grounded in journal and GitHub context.",
            "prompt_version": "v1",
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.generate_seo_revision",
        lambda *_: {
            "draft": "Here is a grounded draft with cleaner formatting.",
            "hashtags": ["#python", "#ai"],
            "rationale": "Formatting and tags improved discoverability.",
            "prompt_version": "v1",
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.generate_remix_draft",
        lambda **_: {
            "draft": "Here is a remixed draft with a tighter opening.",
            "change_summary": "Tightened the opening.",
            "prompt_version": "v1",
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.services.post_history_records.save_last_published_checkpoint",
        lambda **kwargs: {
            "id": "checkpoint-1",
            "checkpoint_type": "last_published_post",
            "post_id": kwargs["post_id"],
            "published_at": kwargs["published_at"].isoformat(),
            "updated_at": kwargs["published_at"].isoformat(),
        },
    )
    reset_settings_cache()
    set_journal_entry_repository(FakeJournalEntryRepository())
    draft_repository = FakeDraftHistoryRepository()
    post_repository = FakePostHistoryRepository()
    set_draft_history_repository(draft_repository)
    set_post_history_repository(post_repository)
    journal_session_store.clear_session(456)
    content_workflow_store.clear_session(456)

    client = TestClient(create_app())

    ideas_response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 50,
            "message": {
                "message_id": 60,
                "text": "/ideas publish flow",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert ideas_response.status_code == 200
    assert ideas_response.json()["dispatch"]["action"] == "ideas_ready"
    assert len(ideas_response.json()["dispatch"]["ideas"]) == 3

    select_response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 51,
            "message": {
                "message_id": 61,
                "text": "/select 2",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert select_response.status_code == 200
    assert select_response.json()["dispatch"]["action"] == "idea_selected"

    draft_response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 52,
            "message": {
                "message_id": 62,
                "text": "/draft",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert draft_response.status_code == 200
    assert draft_response.json()["dispatch"]["action"] == "draft_ready"
    current_draft_id = draft_response.json()["dispatch"]["draft"]["id"]
    assert current_draft_id in draft_repository.documents

    remix_response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 53,
            "message": {
                "message_id": 63,
                "text": "/remix make the opening shorter",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert remix_response.status_code == 200
    assert remix_response.json()["dispatch"]["action"] == "draft_remixed"

    publish_response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 54,
            "message": {
                "message_id": 64,
                "text": "/publish",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["dispatch"]["action"] == "published"
    assert publish_response.json()["dispatch"]["checkpoint"]["checkpoint_type"] == "last_published_post"
    assert len(post_repository.documents) == 1

    history_response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 55,
            "message": {
                "message_id": 65,
                "text": "/history",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert history_response.status_code == 200
    assert history_response.json()["dispatch"]["action"] == "history"
    assert len(history_response.json()["dispatch"]["posts"]) == 1


def _fake_journal_assist_draft():
    return type(
        "Draft",
        (),
        {
            "work_summary": "Worked on Telegram flows.",
            "problem_solved": "Users needed guided capture.",
            "tools_used": "FastAPI and Pydantic.",
            "lesson_learned": "State should stay outside the route.",
            "outcome": "A reviewable journal draft.",
            "why_it_matters": "It improves capture quality.",
            "gaps": ["What problem did you solve?"],
        },
    )()
