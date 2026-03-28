from functools import lru_cache

from pydantic import Field, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


SUPPORTED_LLM_PROVIDERS = {
    "openai",
    "openai_compatible",
    "gemini",
    "anthropic",
}
SUPPORTED_EMBEDDING_PROVIDERS = {
    "openai",
    "openai_compatible",
}


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

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_compatible_api_key: str | None = Field(
        default=None,
        alias="OPENAI_COMPATIBLE_API_KEY",
    )
    openai_compatible_base_url: str | None = Field(
        default=None,
        alias="OPENAI_COMPATIBLE_BASE_URL",
    )
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    idea_provider: str = Field(alias="IDEA_PROVIDER")
    idea_model: str = Field(alias="IDEA_MODEL")
    journal_assist_provider: str = Field(alias="JOURNAL_ASSIST_PROVIDER")
    journal_assist_model: str = Field(alias="JOURNAL_ASSIST_MODEL")
    seo_provider: str = Field(alias="SEO_PROVIDER")
    seo_model: str = Field(alias="SEO_MODEL")
    writer_provider: str = Field(alias="WRITER_PROVIDER")
    writer_model: str = Field(alias="WRITER_MODEL")
    remix_provider: str = Field(alias="REMIX_PROVIDER")
    remix_model: str = Field(alias="REMIX_MODEL")

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
    benchmark_output_path: str = Field(
        default="./reports/benchmarks",
        alias="BENCHMARK_OUTPUT_PATH",
    )
    benchmark_max_cases: int | None = Field(
        default=None,
        alias="BENCHMARK_MAX_CASES",
    )
    benchmark_soft_budget_usd: float | None = Field(
        default=None,
        alias="BENCHMARK_SOFT_BUDGET_USD",
    )
    trace_payload_sampling: bool = Field(
        default=False,
        alias="TRACE_PAYLOAD_SAMPLING",
    )

    @field_validator(
        "idea_provider",
        "journal_assist_provider",
        "seo_provider",
        "writer_provider",
        "remix_provider",
    )
    @classmethod
    def validate_llm_provider(cls, value: str) -> str:
        if value not in SUPPORTED_LLM_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_LLM_PROVIDERS))
            raise ValueError(f"Unsupported LLM provider '{value}'. Expected one of: {supported}.")
        return value

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, value: str) -> str:
        if value not in SUPPORTED_EMBEDDING_PROVIDERS:
            supported = ", ".join(sorted(SUPPORTED_EMBEDDING_PROVIDERS))
            raise ValueError(
                f"Unsupported embedding provider '{value}'. Expected one of: {supported}."
            )
        return value

    @model_validator(mode="after")
    def validate_llm_credentials(self) -> "Settings":
        provider_credentials = {
            "openai": bool(self.openai_api_key),
            "openai_compatible": bool(self.openai_compatible_api_key)
            and bool(self.openai_compatible_base_url),
            "gemini": bool(self.gemini_api_key),
            "anthropic": bool(self.anthropic_api_key),
        }
        task_providers = {
            "IDEA_PROVIDER": self.idea_provider,
            "JOURNAL_ASSIST_PROVIDER": self.journal_assist_provider,
            "SEO_PROVIDER": self.seo_provider,
            "WRITER_PROVIDER": self.writer_provider,
            "REMIX_PROVIDER": self.remix_provider,
        }

        for env_key, provider in task_providers.items():
            if provider_credentials[provider]:
                continue
            if provider == "openai_compatible":
                raise ValueError(
                    f"{env_key} requires OPENAI_COMPATIBLE_API_KEY and OPENAI_COMPATIBLE_BASE_URL."
                )
            required_key = {
                "openai": "OPENAI_API_KEY",
                "gemini": "GEMINI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
            }[provider]
            raise ValueError(f"{env_key} requires {required_key}.")

        if self.embedding_provider == "openai" and not self.openai_api_key:
            raise ValueError("EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY.")
        if self.embedding_provider == "openai_compatible" and (
            not self.openai_compatible_api_key or not self.openai_compatible_base_url
        ):
            raise ValueError(
                "EMBEDDING_PROVIDER=openai_compatible requires OPENAI_COMPATIBLE_API_KEY and OPENAI_COMPATIBLE_BASE_URL."
            )

        return self

    def llm_task_config(self, task: str) -> tuple[str, str]:
        provider = getattr(self, f"{task}_provider")
        model = getattr(self, f"{task}_model")
        return provider, model


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
