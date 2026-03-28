from __future__ import annotations

from datetime import UTC, datetime

from agno.embedder.openai import OpenAIEmbedder

from ai_content_agent.model_telemetry import record_model_call, usage_for_embedding
from ai_content_agent.settings import get_settings


_embedder = None


def build_embedding_vector(
    text: str,
    dimensions: int | None = None,
) -> list[float]:
    settings = get_settings()
    started_at = datetime.now(UTC)
    try:
        embedding = get_embedder().get_embedding(text)
    except Exception as exc:
        finished_at = datetime.now(UTC)
        record_model_call(
            call_type="embedding",
            task="embedding",
            provider=settings.embedding_provider,
            model=settings.embedding_model,
            prompt_version=None,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=(finished_at - started_at).total_seconds() * 1000,
            success=False,
            metrics={},
            raw_output=None,
            output_type=None,
            usage_override=usage_for_embedding(text),
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise

    finished_at = datetime.now(UTC)
    vector = [float(value) for value in embedding]
    record_model_call(
        call_type="embedding",
        task="embedding",
        provider=settings.embedding_provider,
        model=settings.embedding_model,
        prompt_version=None,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=(finished_at - started_at).total_seconds() * 1000,
        success=True,
        metrics={},
        raw_output={"dimensions": len(vector)},
        output_type="list",
        usage_override=usage_for_embedding(text),
    )
    if dimensions is not None and dimensions > 0 and len(embedding) > dimensions:
        return [float(value) for value in embedding[:dimensions]]
    return vector


def get_embedder():
    global _embedder
    if _embedder is None:
        settings = get_settings()
        if settings.embedding_provider == "openai":
            _embedder = OpenAIEmbedder(
                id=settings.embedding_model,
                api_key=settings.openai_api_key,
            )
        elif settings.embedding_provider == "openai_compatible":
            _embedder = OpenAIEmbedder(
                id=settings.embedding_model,
                api_key=settings.openai_compatible_api_key,
                base_url=settings.openai_compatible_base_url,
                request_params={"extra_body": {"provider": {"require_parameters": True}}},
            )
        else:
            raise ValueError(
                "Unsupported embedding provider. Use openai or openai_compatible."
            )
    return _embedder


def set_embedder(embedder) -> None:
    global _embedder
    _embedder = embedder
