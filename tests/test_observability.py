import json
import logging
from pathlib import Path

from fastapi.testclient import TestClient

from ai_content_agent.app import create_app
from ai_content_agent.observability import (
    JsonFormatter,
    REQUEST_ID_HEADER,
    RUN_ID_HEADER,
    TRACE_ID_HEADER,
)
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
    "OPENAI_IDEA_MODEL": "gpt-5",
    "GEMINI_API_KEY": "gemini-key",
    "GEMINI_SEO_MODEL": "gemini-2.5-pro",
    "ANTHROPIC_API_KEY": "anthropic-key",
    "ANTHROPIC_WRITER_MODEL": "claude-sonnet-4",
    "EMBEDDING_PROVIDER": "openai",
    "EMBEDDING_MODEL": "text-embedding-3-large",
}


def test_health_response_includes_request_context_headers(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    client = TestClient(create_app())
    response = client.get("/health", headers={REQUEST_ID_HEADER: "req-123"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers[REQUEST_ID_HEADER] == "req-123"
    assert response.headers[TRACE_ID_HEADER]
    assert response.headers[RUN_ID_HEADER]


def test_request_logging_is_structured(monkeypatch, caplog) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    app = create_app()
    with caplog.at_level(logging.INFO):
        client = TestClient(app)
        response = client.get("/health")

    assert response.status_code == 200

    records = [record for record in caplog.records if record.name == "ai_content_agent.http"]
    assert len(records) == 2
    assert records[0].event == "request.started"
    assert records[1].event == "request.completed"

    payload = json.loads(JsonFormatter().format(records[1]))

    assert payload["event"] == "request.completed"
    assert payload["path"] == "/health"
    assert payload["method"] == "GET"
    assert payload["status_code"] == 200
    assert payload["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert payload["trace_id"] == response.headers[TRACE_ID_HEADER]
    assert payload["run_id"] == response.headers[RUN_ID_HEADER]
