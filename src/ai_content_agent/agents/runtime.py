from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.models.google import Gemini
from agno.models.openai import OpenAIChat

from ai_content_agent.llm import LlmTask, resolve_task_config
from ai_content_agent.settings import Settings, get_settings


@dataclass(frozen=True)
class AgentRunResult:
    content: Any
    model: str | None
    metrics: dict[str, object]


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


def run_agent(agent: Agent, prompt: str) -> AgentRunResult:
    response = agent.run(prompt)
    metrics = getattr(response, "metrics", None) or {}
    return AgentRunResult(
        content=getattr(response, "content", response),
        model=getattr(response, "model", None),
        metrics=dict(metrics) if isinstance(metrics, dict) else {},
    )


def _build_agno_model(provider: str, model_id: str, settings: Settings):
    if provider == "openai":
        return OpenAIChat(id=model_id, api_key=settings.openai_api_key)
    if provider == "openai_compatible":
        return OpenAIChat(
            id=model_id,
            api_key=settings.openai_compatible_api_key,
            base_url=settings.openai_compatible_base_url,
        )
    if provider == "gemini":
        return Gemini(id=model_id, api_key=settings.gemini_api_key)
    if provider == "anthropic":
        return Claude(id=model_id, api_key=settings.anthropic_api_key)
    raise ValueError(f"Unsupported Agno provider: {provider}")
