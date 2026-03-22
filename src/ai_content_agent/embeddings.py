from __future__ import annotations

from agno.embedder.openai import OpenAIEmbedder

from ai_content_agent.settings import get_settings


_embedder = None


def build_embedding_vector(
    text: str,
    dimensions: int | None = None,
) -> list[float]:
    embedding = get_embedder().get_embedding(text)
    if dimensions is not None and dimensions > 0 and len(embedding) > dimensions:
        return [float(value) for value in embedding[:dimensions]]
    return [float(value) for value in embedding]


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
            )
        else:
            raise ValueError(
                "Unsupported embedding provider. Use openai or openai_compatible."
            )
    return _embedder


def set_embedder(embedder) -> None:
    global _embedder
    _embedder = embedder
