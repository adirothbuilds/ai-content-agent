from functools import lru_cache

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(alias="APP_ENV")
    app_host: str = Field(alias="APP_HOST")
    app_port: int = Field(alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    mongodb_uri: str = Field(alias="MONGODB_URI")
    mongodb_database: str = Field(alias="MONGODB_DATABASE")
    mongodb_vector_index_name: str = Field(
        default="default_vector_index",
        alias="MONGODB_VECTOR_INDEX_NAME",
    )

    nats_enabled: bool = Field(default=False, alias="NATS_ENABLED")
    nats_url: str | None = Field(default=None, alias="NATS_URL")

    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str | None = Field(
        default=None,
        alias="TELEGRAM_WEBHOOK_SECRET",
    )
    public_base_url: str = Field(alias="PUBLIC_BASE_URL")
    cloudflared_tunnel_token: str = Field(alias="CLOUDFLARED_TUNNEL_TOKEN")

    github_token: str = Field(alias="GITHUB_TOKEN")
    github_username: str = Field(alias="GITHUB_USERNAME")

    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_idea_model: str = Field(alias="OPENAI_IDEA_MODEL")
    openai_journal_assist_model: str = Field(
        default="gpt-5-mini",
        alias="OPENAI_JOURNAL_ASSIST_MODEL",
    )

    gemini_api_key: str = Field(alias="GEMINI_API_KEY")
    gemini_seo_model: str = Field(alias="GEMINI_SEO_MODEL")

    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")
    anthropic_writer_model: str = Field(alias="ANTHROPIC_WRITER_MODEL")
    anthropic_remix_model: str = Field(
        default="claude-sonnet-4",
        alias="ANTHROPIC_REMIX_MODEL",
    )

    embedding_provider: str = Field(alias="EMBEDDING_PROVIDER")
    embedding_model: str = Field(alias="EMBEDDING_MODEL")

    retrieval_top_k: int = Field(default=8, alias="RETRIEVAL_TOP_K")
    delta_lookback_days_fallback: int = Field(
        default=30,
        alias="DELTA_LOOKBACK_DAYS_FALLBACK",
    )
    post_history_similarity_threshold: float = Field(
        default=0.88,
        alias="POST_HISTORY_SIMILARITY_THRESHOLD",
    )
    enable_provider_benchmarks: bool = Field(
        default=True,
        alias="ENABLE_PROVIDER_BENCHMARKS",
    )
    benchmark_dataset_path: str = Field(
        default="./evals/datasets",
        alias="BENCHMARK_DATASET_PATH",
    )
    trace_payload_sampling: bool = Field(
        default=False,
        alias="TRACE_PAYLOAD_SAMPLING",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        raise RuntimeError(
            "Invalid application configuration. Check required environment "
            "variables in .env."
        ) from exc


def reset_settings_cache() -> None:
    get_settings.cache_clear()
