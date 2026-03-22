import httpx
import pytest

from ai_content_agent.llm import (
    AnthropicAdapter,
    GeminiAdapter,
    LlmAuthenticationError,
    LlmBadRequestError,
    LlmMessage,
    LlmRateLimitError,
    LlmRequest,
    LlmService,
    LlmTask,
    LlmTransientError,
    OpenAiAdapter,
    OpenAiCompatibleAdapter,
    resolve_task_config,
)
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


def test_openai_adapter_returns_shared_response_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer openai-key"
        return httpx.Response(
            200,
            json={
                "model": "gpt-5",
                "choices": [
                    {
                        "message": {"content": "Three grounded ideas"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 8,
                    "total_tokens": 20,
                },
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.openai.com",
    )
    adapter = OpenAiAdapter("openai-key", http_client=client)

    response = adapter.generate(
        LlmRequest(messages=[LlmMessage(role="user", content="Generate ideas")]),
        model="gpt-5",
    )

    assert response.provider == "openai"
    assert response.model == "gpt-5"
    assert response.text == "Three grounded ideas"
    assert response.finish_reason == "stop"
    assert response.usage == {
        "input_tokens": 12,
        "output_tokens": 8,
        "total_tokens": 20,
    }


def test_gemini_adapter_normalizes_rate_limit_errors() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Too many requests"}})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://generativelanguage.googleapis.com",
    )
    adapter = GeminiAdapter("gemini-key", http_client=client)

    with pytest.raises(LlmRateLimitError, match="Too many requests") as exc:
        adapter.generate(
            LlmRequest(messages=[LlmMessage(role="user", content="Optimize SEO")]),
            model="gemini-2.5-pro",
        )

    assert exc.value.provider == "gemini"
    assert exc.value.category == "rate_limit"
    assert exc.value.status_code == 429


def test_openai_compatible_adapter_uses_configured_base_url() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "model": "openrouter/openai/gpt-5-mini",
                "choices": [
                    {
                        "message": {"content": "Routed through compatibility API"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 5,
                    "completion_tokens": 4,
                    "total_tokens": 9,
                },
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://openrouter.ai/api",
    )
    adapter = OpenAiCompatibleAdapter(
        "router-key",
        http_client=client,
        base_url="https://openrouter.ai/api",
    )

    response = adapter.generate(
        LlmRequest(messages=[LlmMessage(role="user", content="Help me write")]),
        model="openrouter/openai/gpt-5-mini",
    )

    assert response.provider == "openai_compatible"
    assert response.text == "Routed through compatibility API"
    assert requests[0].headers["Authorization"] == "Bearer router-key"
    assert str(requests[0].url) == "https://openrouter.ai/api/v1/chat/completions"


def test_anthropic_adapter_normalizes_authentication_errors() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.anthropic.com",
    )
    adapter = AnthropicAdapter("anthropic-key", http_client=client)

    with pytest.raises(LlmAuthenticationError, match="Invalid API key") as exc:
        adapter.generate(
            LlmRequest(messages=[LlmMessage(role="user", content="Write a draft")]),
            model="claude-sonnet-4",
        )

    assert exc.value.provider == "anthropic"
    assert exc.value.category == "authentication"
    assert exc.value.status_code == 401


def test_service_routes_task_to_matching_adapter() -> None:
    settings = build_settings()

    class StubAdapter:
        def __init__(self, provider: str) -> None:
            self.provider = provider
            self.calls: list[tuple[str, LlmRequest]] = []

        def generate(self, request: LlmRequest, model: str):
            self.calls.append((model, request))
            return type(
                "StubResponse",
                (),
                {
                    "provider": self.provider,
                    "model": model,
                    "text": f"{self.provider}:{model}",
                    "finish_reason": "stop",
                    "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                    "raw": {},
                },
            )()

    openai = StubAdapter("openai")
    openai_compatible = StubAdapter("openai_compatible")
    gemini = StubAdapter("gemini")
    anthropic = StubAdapter("anthropic")
    service = LlmService(
        settings,
        openai_adapter=openai,
        openai_compatible_adapter=openai_compatible,
        gemini_adapter=gemini,
        anthropic_adapter=anthropic,
    )
    request = LlmRequest(messages=[LlmMessage(role="user", content="hello")])

    idea_response = service.generate_for_task(LlmTask.IDEA, request)
    journal_response = service.generate_for_task(LlmTask.JOURNAL_ASSIST, request)
    seo_response = service.generate_for_task(LlmTask.SEO, request)
    writer_response = service.generate_for_task(LlmTask.WRITER, request)
    remix_response = service.generate_for_task(LlmTask.REMIX, request)

    assert idea_response.text == "openai:gpt-5"
    assert journal_response.text == "openai_compatible:openrouter/openai/gpt-5-mini"
    assert seo_response.text == "gemini:gemini-2.5-pro"
    assert writer_response.text == "anthropic:claude-sonnet-4"
    assert remix_response.text == "openai:gpt-5"
    assert openai.calls[0][0] == "gpt-5"
    assert openai_compatible.calls[0][0] == "openrouter/openai/gpt-5-mini"
    assert gemini.calls[0][0] == "gemini-2.5-pro"
    assert anthropic.calls[0][0] == "claude-sonnet-4"


def test_request_transport_errors_are_normalized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.openai.com",
    )
    adapter = OpenAiAdapter("openai-key", http_client=client)

    with pytest.raises(LlmTransientError, match="network down") as exc:
        adapter.generate(
            LlmRequest(messages=[LlmMessage(role="user", content="Generate ideas")]),
            model="gpt-5",
        )

    assert exc.value.provider == "openai"
    assert exc.value.category == "transient"


def test_bad_request_errors_are_normalized() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "Bad prompt"}})

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.openai.com",
    )
    adapter = OpenAiAdapter("openai-key", http_client=client)

    with pytest.raises(LlmBadRequestError, match="Bad prompt") as exc:
        adapter.generate(
            LlmRequest(messages=[LlmMessage(role="user", content="Generate ideas")]),
            model="gpt-5",
        )

    assert exc.value.provider == "openai"
    assert exc.value.category == "bad_request"
