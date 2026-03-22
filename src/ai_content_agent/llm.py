from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

from ai_content_agent.settings import Settings, get_settings


class LlmTask(StrEnum):
    IDEA = "idea"
    JOURNAL_ASSIST = "journal_assist"
    SEO = "seo"
    WRITER = "writer"
    REMIX = "remix"


class LlmProvider(StrEnum):
    OPENAI = "openai"
    OPENAI_COMPATIBLE = "openai_compatible"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"


@dataclass(frozen=True)
class LlmMessage:
    role: str
    content: str


@dataclass(frozen=True)
class LlmRequest:
    messages: list[LlmMessage]
    temperature: float | None = None
    max_output_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LlmResponse:
    provider: str
    model: str
    text: str
    finish_reason: str | None
    usage: dict[str, int]
    raw: dict[str, Any]


class LlmProviderError(RuntimeError):
    def __init__(
        self,
        *,
        provider: str,
        message: str,
        category: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.category = category
        self.status_code = status_code


class LlmAuthenticationError(LlmProviderError):
    pass


class LlmBadRequestError(LlmProviderError):
    pass


class LlmRateLimitError(LlmProviderError):
    pass


class LlmTransientError(LlmProviderError):
    pass


@dataclass(frozen=True)
class LlmTaskConfig:
    task: LlmTask
    provider: LlmProvider
    model: str


def resolve_task_config(
    task: LlmTask,
    settings: Settings | None = None,
) -> LlmTaskConfig:
    resolved_settings = settings or get_settings()
    provider_name, model = resolved_settings.llm_task_config(task.value)
    return LlmTaskConfig(
        task=task,
        provider=LlmProvider(provider_name),
        model=model,
    )


class LlmAdapter:
    provider: LlmProvider

    def generate(self, request: LlmRequest, model: str) -> LlmResponse:
        raise NotImplementedError


class OpenAiAdapter(LlmAdapter):
    provider = LlmProvider.OPENAI

    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.Client | None = None,
        base_url: str = "https://api.openai.com",
    ) -> None:
        self._http_client = http_client or httpx.Client(
            base_url=base_url,
            timeout=30.0,
        )
        self._owns_client = http_client is None
        self._api_key = api_key

    def close(self) -> None:
        if self._owns_client:
            self._http_client.close()

    def generate(self, request: LlmRequest, model: str) -> LlmResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in request.messages
            ],
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            payload["max_completion_tokens"] = request.max_output_tokens

        response = self._request(
            "POST",
            "/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        body = response.json()
        choice = body["choices"][0]
        usage = body.get("usage", {})
        return LlmResponse(
            provider=self.provider.value,
            model=body.get("model", model),
            text=_extract_openai_text(choice.get("message", {}).get("content")),
            finish_reason=choice.get("finish_reason"),
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            raw=body,
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._http_client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            raise LlmTransientError(
                provider=self.provider.value,
                message=f"{self.provider.value} request failed: {exc}",
                category="transient",
            ) from exc
        _raise_for_status(self.provider, response)
        return response


class OpenAiCompatibleAdapter(OpenAiAdapter):
    provider = LlmProvider.OPENAI_COMPATIBLE


class GeminiAdapter(LlmAdapter):
    provider = LlmProvider.GEMINI

    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.Client | None = None,
        base_url: str = "https://generativelanguage.googleapis.com",
    ) -> None:
        self._http_client = http_client or httpx.Client(
            base_url=base_url,
            timeout=30.0,
        )
        self._owns_client = http_client is None
        self._api_key = api_key

    def close(self) -> None:
        if self._owns_client:
            self._http_client.close()

    def generate(self, request: LlmRequest, model: str) -> LlmResponse:
        system_parts = [
            {"text": message.content}
            for message in request.messages
            if message.role == "system"
        ]
        contents = [
            {
                "role": "model" if message.role == "assistant" else "user",
                "parts": [{"text": message.content}],
            }
            for message in request.messages
            if message.role != "system"
        ]
        payload: dict[str, Any] = {"contents": contents}
        if system_parts:
            payload["system_instruction"] = {"parts": system_parts}
        generation_config: dict[str, Any] = {}
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.max_output_tokens is not None:
            generation_config["maxOutputTokens"] = request.max_output_tokens
        if generation_config:
            payload["generationConfig"] = generation_config

        response = self._request(
            "POST",
            f"/v1beta/models/{model}:generateContent",
            params={"key": self._api_key},
            json=payload,
        )
        body = response.json()
        candidate = body["candidates"][0]
        parts = candidate.get("content", {}).get("parts", [])
        usage = body.get("usageMetadata", {})
        return LlmResponse(
            provider=self.provider.value,
            model=model,
            text="".join(part.get("text", "") for part in parts),
            finish_reason=candidate.get("finishReason"),
            usage={
                "input_tokens": usage.get("promptTokenCount", 0),
                "output_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": usage.get("totalTokenCount", 0),
            },
            raw=body,
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._http_client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            raise LlmTransientError(
                provider=self.provider.value,
                message=f"Gemini request failed: {exc}",
                category="transient",
            ) from exc
        _raise_for_status(self.provider, response)
        return response


class AnthropicAdapter(LlmAdapter):
    provider = LlmProvider.ANTHROPIC

    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.Client | None = None,
        base_url: str = "https://api.anthropic.com",
    ) -> None:
        self._http_client = http_client or httpx.Client(
            base_url=base_url,
            timeout=30.0,
        )
        self._owns_client = http_client is None
        self._api_key = api_key

    def close(self) -> None:
        if self._owns_client:
            self._http_client.close()

    def generate(self, request: LlmRequest, model: str) -> LlmResponse:
        system_text = "\n\n".join(
            message.content
            for message in request.messages
            if message.role == "system"
        )
        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": request.max_output_tokens or 1024,
            "messages": [
                {
                    "role": "assistant" if message.role == "assistant" else "user",
                    "content": message.content,
                }
                for message in request.messages
                if message.role != "system"
            ],
        }
        if system_text:
            payload["system"] = system_text
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        response = self._request(
            "POST",
            "/v1/messages",
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
        body = response.json()
        usage = body.get("usage", {})
        return LlmResponse(
            provider=self.provider.value,
            model=body.get("model", model),
            text="".join(
                block.get("text", "")
                for block in body.get("content", [])
                if block.get("type") == "text"
            ),
            finish_reason=body.get("stop_reason"),
            usage={
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "total_tokens": (
                    usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                ),
            },
            raw=body,
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._http_client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            raise LlmTransientError(
                provider=self.provider.value,
                message=f"Anthropic request failed: {exc}",
                category="transient",
            ) from exc
        _raise_for_status(self.provider, response)
        return response


class LlmService:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        openai_adapter: OpenAiAdapter | None = None,
        openai_compatible_adapter: OpenAiCompatibleAdapter | None = None,
        gemini_adapter: GeminiAdapter | None = None,
        anthropic_adapter: AnthropicAdapter | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._adapters: dict[LlmProvider, LlmAdapter] = {}
        self._adapter_overrides: dict[LlmProvider, LlmAdapter | None] = {
            LlmProvider.OPENAI: openai_adapter,
            LlmProvider.OPENAI_COMPATIBLE: openai_compatible_adapter,
            LlmProvider.GEMINI: gemini_adapter,
            LlmProvider.ANTHROPIC: anthropic_adapter,
        }

    def generate_for_task(
        self,
        task: LlmTask,
        request: LlmRequest,
    ) -> LlmResponse:
        task_config = resolve_task_config(task, self._settings)
        adapter = self._get_adapter(task_config.provider)
        return adapter.generate(request=request, model=task_config.model)

    def _get_adapter(self, provider: LlmProvider) -> LlmAdapter:
        adapter = self._adapters.get(provider)
        if adapter is not None:
            return adapter

        override = self._adapter_overrides.get(provider)
        if override is not None:
            self._adapters[provider] = override
            return override

        if provider == LlmProvider.OPENAI:
            adapter = OpenAiAdapter(self._settings.openai_api_key or "")
        elif provider == LlmProvider.OPENAI_COMPATIBLE:
            adapter = OpenAiCompatibleAdapter(
                self._settings.openai_compatible_api_key or "",
                base_url=self._settings.openai_compatible_base_url or "",
            )
        elif provider == LlmProvider.GEMINI:
            adapter = GeminiAdapter(self._settings.gemini_api_key or "")
        else:
            adapter = AnthropicAdapter(self._settings.anthropic_api_key or "")

        self._adapters[provider] = adapter
        return adapter


def build_llm_service(settings: Settings | None = None) -> LlmService:
    return LlmService(settings=settings)


def _extract_openai_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        return "".join(text_parts)
    return ""


def _raise_for_status(provider: LlmProvider, response: httpx.Response) -> None:
    if response.is_success:
        return

    message = _extract_error_message(response)
    status_code = response.status_code
    provider_name = provider.value
    if status_code in {401, 403}:
        raise LlmAuthenticationError(
            provider=provider_name,
            message=message,
            category="authentication",
            status_code=status_code,
        )
    if status_code in {400, 404, 422}:
        raise LlmBadRequestError(
            provider=provider_name,
            message=message,
            category="bad_request",
            status_code=status_code,
        )
    if status_code in {408, 429}:
        raise LlmRateLimitError(
            provider=provider_name,
            message=message,
            category="rate_limit",
            status_code=status_code,
        )
    raise LlmTransientError(
        provider=provider_name,
        message=message,
        category="transient",
        status_code=status_code,
    )


def _extract_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Provider request failed with status {response.status_code}."

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
        message = payload.get("message")
        if isinstance(message, str) and message:
            return message

    return f"Provider request failed with status {response.status_code}."
