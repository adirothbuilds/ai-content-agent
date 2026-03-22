from pathlib import Path

from fastapi.testclient import TestClient

from ai_content_agent.app import create_app
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


def test_telegram_webhook_parses_command(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

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
        "action": {
            "type": "command",
            "chat_id": 123,
            "user_id": 99,
            "command": "start",
            "text": "/start hello",
            "update_id": 1,
        },
    }


def test_telegram_webhook_rejects_invalid_secret(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "expected-secret")
    reset_settings_cache()

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
        "action": {
            "type": "message",
            "chat_id": 456,
            "user_id": 100,
            "command": None,
            "text": "plain text",
            "update_id": 2,
        },
    }
