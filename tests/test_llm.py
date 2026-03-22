from ai_content_agent.llm import LlmTask, resolve_task_config
from ai_content_agent.settings import Settings


def build_settings() -> Settings:
    return Settings.model_validate(
        {
            "APP_ENV": "development",
            "APP_HOST": "0.0.0.0",
            "APP_PORT": 8000,
            "LOG_LEVEL": "INFO",
            "MONGODB_URI": "mongodb://mongodb:27017",
            "MONGODB_DATABASE": "ai_content_agent",
            "TELEGRAM_BOT_TOKEN": "telegram-token",
            "PUBLIC_BASE_URL": "https://example.com",
            "CLOUDFLARED_TUNNEL_TOKEN": "cloudflare-token",
            "GITHUB_TOKEN": "github-token",
            "GITHUB_USERNAME": "adiroth",
            "OPENAI_API_KEY": "openai-key",
            "OPENAI_COMPATIBLE_API_KEY": "router-key",
            "OPENAI_COMPATIBLE_BASE_URL": "https://openrouter.ai/api",
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
            "REMIX_PROVIDER": "openai",
            "REMIX_MODEL": "gpt-5",
            "EMBEDDING_PROVIDER": "openai",
            "EMBEDDING_MODEL": "text-embedding-3-large",
        }
    )


def test_resolve_task_config_uses_expected_provider_and_model() -> None:
    settings = build_settings()

    idea = resolve_task_config(LlmTask.IDEA, settings)
    journal = resolve_task_config(LlmTask.JOURNAL_ASSIST, settings)
    seo = resolve_task_config(LlmTask.SEO, settings)
    writer = resolve_task_config(LlmTask.WRITER, settings)
    remix = resolve_task_config(LlmTask.REMIX, settings)

    assert idea.provider.value == "openai"
    assert idea.model == "gpt-5"
    assert journal.provider.value == "openai_compatible"
    assert journal.model == "openrouter/openai/gpt-5-mini"
    assert seo.provider.value == "gemini"
    assert seo.model == "gemini-2.5-pro"
    assert writer.provider.value == "anthropic"
    assert writer.model == "claude-sonnet-4"
    assert remix.provider.value == "openai"
    assert remix.model == "gpt-5"
