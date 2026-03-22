from datetime import UTC, datetime
from pathlib import Path

from ai_content_agent.services.checkpoints import (
    resolve_activity_since,
    save_last_published_checkpoint,
    set_checkpoint_repository,
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


class FakeCheckpointRepository:
    def __init__(self) -> None:
        self.document = None

    def get_last_published_checkpoint(self):
        return self.document

    def save_last_published_checkpoint(self, document) -> None:
        self.document = dict(document)


def test_resolve_activity_since_uses_last_published_checkpoint(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    repository = FakeCheckpointRepository()
    repository.document = {
        "checkpoint_type": "last_published_post",
        "published_at": "2026-03-20T10:00:00+00:00",
    }
    set_checkpoint_repository(repository)

    since = resolve_activity_since(now=datetime(2026, 3, 22, tzinfo=UTC))

    assert since == datetime(2026, 3, 20, 10, 0, tzinfo=UTC)


def test_resolve_activity_since_falls_back_when_checkpoint_missing(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("DELTA_LOOKBACK_DAYS_FALLBACK", "7")
    reset_settings_cache()

    repository = FakeCheckpointRepository()
    set_checkpoint_repository(repository)

    now = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)
    since = resolve_activity_since(now=now)

    assert since == datetime(2026, 3, 15, 12, 0, tzinfo=UTC)


def test_resolve_activity_since_returns_none_for_explicit_topic_request(
    monkeypatch,
) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    repository = FakeCheckpointRepository()
    repository.document = {
        "checkpoint_type": "last_published_post",
        "published_at": "2026-03-20T10:00:00+00:00",
    }
    set_checkpoint_repository(repository)

    since = resolve_activity_since(explicit_topic_requested=True)

    assert since is None


def test_save_last_published_checkpoint_persists_document(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    repository = FakeCheckpointRepository()
    set_checkpoint_repository(repository)

    document = save_last_published_checkpoint(
        published_at=datetime(2026, 3, 22, 13, 0, tzinfo=UTC),
        post_id="post-123",
    )

    assert document["checkpoint_type"] == "last_published_post"
    assert document["post_id"] == "post-123"
    assert repository.document is not None
    assert repository.document["published_at"] == "2026-03-22T13:00:00+00:00"
