from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

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
