from pathlib import Path
from datetime import UTC, datetime
from types import SimpleNamespace

from ai_content_agent.agents.runtime import _build_agno_model
from ai_content_agent.embeddings import build_embedding_vector, set_embedder
from ai_content_agent.model_telemetry import (
    clear_model_call_records,
    get_model_call_records,
    record_model_call,
    update_model_call_record,
    usage_from_metrics,
)
from ai_content_agent.settings import Settings, reset_settings_cache


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
    "OPENAI_API_KEY": "",
    "OPENAI_COMPATIBLE_API_KEY": "router-key",
    "OPENAI_COMPATIBLE_BASE_URL": "https://openrouter.ai/api/v1",
    "GEMINI_API_KEY": "",
    "ANTHROPIC_API_KEY": "",
    "IDEA_PROVIDER": "openai_compatible",
    "IDEA_MODEL": "openai/gpt-5-mini",
    "JOURNAL_ASSIST_PROVIDER": "openai_compatible",
    "JOURNAL_ASSIST_MODEL": "openai/gpt-5-mini",
    "SEO_PROVIDER": "openai_compatible",
    "SEO_MODEL": "google/gemini-2.5-pro",
    "WRITER_PROVIDER": "openai_compatible",
    "WRITER_MODEL": "anthropic/claude-sonnet-4",
    "REMIX_PROVIDER": "openai_compatible",
    "REMIX_MODEL": "anthropic/claude-sonnet-4",
    "EMBEDDING_PROVIDER": "openai_compatible",
    "EMBEDDING_MODEL": "text-embedding-3-small",
}


def _set_environment(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()


def test_openrouter_model_and_embedder_require_parameters(monkeypatch) -> None:
    _set_environment(monkeypatch)
    settings = Settings()

    model = _build_agno_model("openai_compatible", "openai/gpt-5-mini", settings)

    assert model.request_params == {
        "extra_body": {"provider": {"require_parameters": True}}
    }


def test_openrouter_non_openai_model_does_not_force_require_parameters(monkeypatch) -> None:
    _set_environment(monkeypatch)
    settings = Settings()

    model = _build_agno_model("openai_compatible", "anthropic/claude-sonnet-4", settings)

    assert model.request_params is None


def test_embedding_records_model_call(monkeypatch) -> None:
    _set_environment(monkeypatch)
    clear_model_call_records()
    set_embedder(SimpleNamespace(get_embedding=lambda text: [0.1, 0.2, 0.3]))

    vector = build_embedding_vector("Telemetry for embeddings.")
    records = get_model_call_records()

    assert vector == [0.1, 0.2, 0.3]
    assert len(records) == 1
    assert records[0]["call_type"] == "embedding"
    assert records[0]["usage"]["input_tokens"] > 0
    assert records[0]["estimated_cost_usd"] is not None

    set_embedder(None)
    clear_model_call_records()


def test_model_call_record_can_be_updated() -> None:
    clear_model_call_records()
    record_id = record_model_call(
        call_type="llm",
        task="writer",
        provider="openai_compatible",
        model="anthropic/claude-sonnet-4",
        prompt_version="v1",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        duration_ms=12.34,
        success=True,
        metrics={"input_tokens": [100], "output_tokens": [50], "total_tokens": [150]},
        structured_output_expected=True,
    )

    update_model_call_record(
        record_id,
        structured_output_observed=False,
        fallback_used=True,
    )
    record = get_model_call_records()[0]

    assert record["usage"] == usage_from_metrics({"input_tokens": [100], "output_tokens": [50], "total_tokens": [150]}).__dict__
    assert record["structured_output_observed"] is False
    assert record["fallback_used"] is True
