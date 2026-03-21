from pathlib import Path

import pytest

from ai_content_agent.settings import Settings, get_settings, reset_settings_cache


REQUIRED_ENVIRONMENT = {
    "APP_ENV": "development",
    "APP_HOST": "0.0.0.0",
    "APP_PORT": "8000",
    "MONGODB_URI": "mongodb://mongodb:27017",
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


@pytest.fixture(autouse=True)
def clear_settings_cache():
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_settings_load_from_environment(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in REQUIRED_ENVIRONMENT.items():
        monkeypatch.setenv(key, value)

    settings = Settings()

    assert settings.app_env == "development"
    assert settings.app_host == "0.0.0.0"
    assert settings.app_port == 8000
    assert settings.log_level == "INFO"
    assert settings.mongodb_vector_index_name == "default_vector_index"
    assert settings.nats_enabled is False
    assert settings.openai_journal_assist_model == "gpt-5-mini"
    assert settings.anthropic_remix_model == "claude-sonnet-4"
    assert settings.retrieval_top_k == 8
    assert settings.delta_lookback_days_fallback == 30
    assert settings.post_history_similarity_threshold == 0.88
    assert settings.enable_provider_benchmarks is True
    assert settings.benchmark_dataset_path == "./evals/datasets"
    assert settings.trace_payload_sampling is False


def test_get_settings_fails_clearly_when_required_values_are_missing(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key in REQUIRED_ENVIRONMENT:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match="Invalid application configuration"):
        get_settings()
