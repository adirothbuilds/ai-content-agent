from pathlib import Path

import pytest
from pydantic import ValidationError

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
    "GEMINI_API_KEY": "gemini-key",
    "ANTHROPIC_API_KEY": "anthropic-key",
    "IDEA_PROVIDER": "openai",
    "IDEA_MODEL": "gpt-5",
    "JOURNAL_ASSIST_PROVIDER": "openai_compatible",
    "JOURNAL_ASSIST_MODEL": "openrouter/openai/gpt-5-mini",
    "SEO_PROVIDER": "gemini",
    "SEO_MODEL": "gemini-2.5-pro",
    "WRITER_PROVIDER": "anthropic",
    "WRITER_MODEL": "claude-sonnet-4",
    "REMIX_PROVIDER": "anthropic",
    "REMIX_MODEL": "claude-sonnet-4",
    "OPENAI_COMPATIBLE_API_KEY": "router-key",
    "OPENAI_COMPATIBLE_BASE_URL": "https://openrouter.ai/api",
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
    assert settings.idea_provider == "openai"
    assert settings.journal_assist_provider == "openai_compatible"
    assert settings.journal_assist_model == "openrouter/openai/gpt-5-mini"
    assert settings.remix_provider == "anthropic"
    assert settings.remix_model == "claude-sonnet-4"
    assert settings.retrieval_top_k == 8
    assert settings.delta_lookback_days_fallback == 30
    assert settings.post_history_similarity_threshold == 0.88
    assert settings.enable_provider_benchmarks is True
    assert settings.benchmark_dataset_path == "./evals/datasets"
    assert settings.benchmark_output_path == "./reports/benchmarks"
    assert settings.benchmark_max_cases is None
    assert settings.benchmark_soft_budget_usd is None
    assert settings.trace_payload_sampling is False


def test_settings_reject_unsupported_llm_provider(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in REQUIRED_ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("IDEA_PROVIDER", "grok")

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        Settings()


def test_settings_require_credentials_for_selected_provider(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in REQUIRED_ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)

    with pytest.raises(
        ValueError,
        match="JOURNAL_ASSIST_PROVIDER requires OPENAI_COMPATIBLE_API_KEY and OPENAI_COMPATIBLE_BASE_URL",
    ):
        Settings()


def test_settings_hard_cutover_requires_new_task_keys(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in REQUIRED_ENVIRONMENT.items():
        if key not in {
            "IDEA_PROVIDER",
            "IDEA_MODEL",
            "JOURNAL_ASSIST_PROVIDER",
            "JOURNAL_ASSIST_MODEL",
            "SEO_PROVIDER",
            "SEO_MODEL",
            "WRITER_PROVIDER",
            "WRITER_MODEL",
            "REMIX_PROVIDER",
            "REMIX_MODEL",
        }:
            monkeypatch.setenv(key, value)
    monkeypatch.setenv("OPENAI_IDEA_MODEL", "legacy-gpt-5")

    with pytest.raises(ValidationError):
        Settings()


def test_get_settings_fails_clearly_when_required_values_are_missing(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key in REQUIRED_ENVIRONMENT:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match="Invalid application configuration"):
        get_settings()
