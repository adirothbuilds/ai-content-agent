from pathlib import Path

from fastapi.testclient import TestClient

from ai_content_agent.app import create_app
from ai_content_agent.services.journal_entries import set_journal_entry_repository
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
    "OPENAI_IDEA_MODEL": "gpt-5",
    "GEMINI_API_KEY": "gemini-key",
    "GEMINI_SEO_MODEL": "gemini-2.5-pro",
    "ANTHROPIC_API_KEY": "anthropic-key",
    "ANTHROPIC_WRITER_MODEL": "claude-sonnet-4",
    "EMBEDDING_PROVIDER": "openai",
    "EMBEDDING_MODEL": "text-embedding-3-large",
}


class FakeJournalEntryRepository:
    def __init__(self) -> None:
        self.documents: list[dict[str, object]] = []

    def save(self, document) -> None:
        self.documents.append(dict(document))


def test_telegram_webhook_parses_command(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()
    set_journal_entry_repository(FakeJournalEntryRepository())

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
            "message": "Unsupported command. Use /journal, /assist, /accept_ai, /reject_ai, /review, /save, or /cancel.",
        },
    }


def test_telegram_webhook_rejects_invalid_secret(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "expected-secret")
    reset_settings_cache()
    set_journal_entry_repository(FakeJournalEntryRepository())

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
    reset_settings_cache()
    repository = FakeJournalEntryRepository()
    set_journal_entry_repository(repository)

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
    reset_settings_cache()
    repository = FakeJournalEntryRepository()
    set_journal_entry_repository(repository)

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
