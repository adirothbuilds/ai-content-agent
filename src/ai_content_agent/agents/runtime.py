from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat
from pydantic import BaseModel

from ai_content_agent.llm import LlmTask, resolve_task_config
from ai_content_agent.model_telemetry import record_model_call
from ai_content_agent.settings import Settings, get_settings


@dataclass(frozen=True)
class AgentRunResult:
    content: Any
    model: str | None
    metrics: dict[str, object]
    record_id: str | None = None


def build_agno_agent(
    *,
    task: LlmTask,
    instructions: str | list[str],
    response_model: type | None = None,
    settings: Settings | None = None,
) -> Agent:
    resolved_settings = settings or get_settings()
    task_config = resolve_task_config(task, resolved_settings)
    return Agent(
        model=_build_agno_model(task_config.provider.value, task_config.model, resolved_settings),
        instructions=instructions,
        response_model=response_model,
        markdown=False,
    )


def run_agent(
    agent: Agent,
    prompt: str,
    *,
    task: LlmTask,
    provider: str,
    model: str,
    prompt_version: str | None,
    structured_output_expected: bool,
) -> AgentRunResult:
    started_at = datetime.now(UTC)
    try:
        response = agent.run(prompt)
    except Exception as exc:
        finished_at = datetime.now(UTC)
        record_id = record_model_call(
            call_type="llm",
            task=task.value,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=(finished_at - started_at).total_seconds() * 1000,
            success=False,
            metrics={},
            structured_output_expected=structured_output_expected,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise

    finished_at = datetime.now(UTC)
    metrics = getattr(response, "metrics", None) or {}
    content = getattr(response, "content", response)
    record_id = record_model_call(
        call_type="llm",
        task=task.value,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=(finished_at - started_at).total_seconds() * 1000,
        success=True,
        metrics=dict(metrics) if isinstance(metrics, dict) else {},
        structured_output_expected=structured_output_expected,
        raw_output=content,
        output_type=type(content).__name__,
    )
    return AgentRunResult(
        content=content,
        model=getattr(response, "model", None),
        metrics=dict(metrics) if isinstance(metrics, dict) else {},
        record_id=record_id,
    )


def coerce_response_model_output(content: Any, response_model: type[BaseModel]) -> BaseModel:
    if isinstance(content, response_model):
        return content

    if isinstance(content, BaseModel):
        return response_model.model_validate(content.model_dump())

    if hasattr(content, "model_dump") and callable(content.model_dump):
        return response_model.model_validate(content.model_dump())

    if isinstance(content, dict):
        return response_model.model_validate(content)

    if isinstance(content, str):
        try:
            return response_model.model_validate_json(content)
        except Exception:
            extracted = _extract_json_object(content)
            if extracted is not None:
                return response_model.model_validate(extracted)

    raise TypeError(
        f"Could not coerce agent output into {response_model.__name__}. "
        f"Received {type(content).__name__}."
    )


def _build_agno_model(provider: str, model_id: str, settings: Settings):
    if provider == "openai":
        return OpenAIChat(id=model_id, api_key=settings.openai_api_key)
    if provider == "openai_compatible":
        request_params = None
        if _should_require_openrouter_parameters(model_id):
            request_params = {"extra_body": {"provider": {"require_parameters": True}}}
        return OpenAIChat(
            id=model_id,
            api_key=settings.openai_compatible_api_key,
            base_url=settings.openai_compatible_base_url,
            request_params=request_params,
        )
    if provider == "gemini":
        return Gemini(id=model_id, api_key=settings.gemini_api_key)
    if provider == "anthropic":
        return Claude(id=model_id, api_key=settings.anthropic_api_key)
    raise ValueError(f"Unsupported Agno provider: {provider}")


def _extract_json_object(content: str) -> dict[str, Any] | list[Any] | None:
    candidates = [content.strip()]
    fenced_match = re.search(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
    if fenced_match:
        candidates.append(fenced_match.group(1).strip())

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                pass

        start = candidate.find("[")
        end = candidate.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                pass

    return None


def _should_require_openrouter_parameters(model_id: str) -> bool:
    return model_id.startswith("openai/")
