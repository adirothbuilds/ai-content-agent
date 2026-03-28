from __future__ import annotations

import contextvars
import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from ai_content_agent.observability import get_request_context


_model_call_records_var: contextvars.ContextVar[list["ModelCallRecord"]] = contextvars.ContextVar(
    "model_call_records",
    default=[],
)


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass(frozen=True)
class ModelCallRecord:
    id: str
    call_type: str
    task: str
    provider: str
    model: str
    prompt_version: str | None
    request_id: str | None
    trace_id: str | None
    run_id: str | None
    started_at: str
    finished_at: str
    duration_ms: float
    success: bool
    structured_output_expected: bool
    structured_output_observed: bool | None
    fallback_used: bool
    usage: ModelUsage
    estimated_cost_usd: float | None
    metrics: dict[str, object] = field(default_factory=dict)
    raw_output: object | None = None
    output_type: str | None = None
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["estimated_cost_usd"] = _round_optional(payload["estimated_cost_usd"])
        return payload


def clear_model_call_records() -> None:
    _model_call_records_var.set([])


def get_model_call_records() -> list[dict[str, object]]:
    return [record.to_dict() for record in _model_call_records_var.get()]


def record_model_call(
    *,
    call_type: str,
    task: str,
    provider: str,
    model: str,
    prompt_version: str | None,
    started_at: datetime,
    finished_at: datetime,
    duration_ms: float,
    success: bool,
    metrics: dict[str, object] | None = None,
    structured_output_expected: bool = False,
    structured_output_observed: bool | None = None,
    fallback_used: bool = False,
    raw_output: object | None = None,
    output_type: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    usage_override: ModelUsage | None = None,
) -> str:
    usage = usage_override or usage_from_metrics(metrics or {})
    context = get_request_context()
    record = ModelCallRecord(
        id=str(uuid4()),
        call_type=call_type,
        task=task,
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        request_id=context["request_id"],
        trace_id=context["trace_id"],
        run_id=context["run_id"],
        started_at=started_at.astimezone(UTC).isoformat(),
        finished_at=finished_at.astimezone(UTC).isoformat(),
        duration_ms=round(duration_ms, 2),
        success=success,
        structured_output_expected=structured_output_expected,
        structured_output_observed=structured_output_observed,
        fallback_used=fallback_used,
        usage=usage,
        estimated_cost_usd=estimate_cost_usd(provider=provider, model=model, usage=usage),
        metrics=dict(metrics or {}),
        raw_output=serialize_output(raw_output),
        output_type=output_type,
        error_type=error_type,
        error_message=error_message,
    )
    _model_call_records_var.set([*_model_call_records_var.get(), record])
    return record.id


def update_model_call_record(record_id: str, **updates: object) -> None:
    updated_records: list[ModelCallRecord] = []
    for record in _model_call_records_var.get():
        if record.id != record_id:
            updated_records.append(record)
            continue
        payload = record.to_dict()
        payload.update(updates)
        if "usage" in payload and isinstance(payload["usage"], dict):
            payload["usage"] = ModelUsage(**payload["usage"])
        updated_records.append(ModelCallRecord(**payload))
    _model_call_records_var.set(updated_records)


def usage_from_metrics(metrics: dict[str, object]) -> ModelUsage:
    return ModelUsage(
        input_tokens=_extract_metric_int(metrics, "input_tokens"),
        output_tokens=_extract_metric_int(metrics, "output_tokens"),
        total_tokens=_extract_metric_int(metrics, "total_tokens"),
        prompt_tokens=_extract_metric_int(metrics, "prompt_tokens"),
        completion_tokens=_extract_metric_int(metrics, "completion_tokens"),
        cached_tokens=_extract_metric_int(metrics, "cached_tokens"),
        reasoning_tokens=_extract_metric_int(metrics, "reasoning_tokens"),
    )


def usage_for_embedding(text: str) -> ModelUsage:
    estimated_input_tokens = max(1, math.ceil(len(text) / 4))
    return ModelUsage(
        input_tokens=estimated_input_tokens,
        prompt_tokens=estimated_input_tokens,
        total_tokens=estimated_input_tokens,
    )


def serialize_output(value: object) -> object:
    if value is None:
        return None
    if hasattr(value, "model_dump") and callable(value.model_dump):
        return value.model_dump()
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): serialize_output(item) for key, item in value.items()}
    if isinstance(value, list):
        return [serialize_output(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_output(item) for item in value]
    return str(value)


def estimate_cost_usd(*, provider: str, model: str, usage: ModelUsage) -> float | None:
    pricing = _pricing_for_model(provider=provider, model=model)
    if not pricing:
        return None

    input_tokens = usage.input_tokens or usage.prompt_tokens or 0
    output_tokens = usage.output_tokens or usage.completion_tokens or 0
    total = 0.0

    if pricing.get("input_per_million") is not None:
        total += (input_tokens / 1_000_000) * float(pricing["input_per_million"])
    if pricing.get("output_per_million") is not None:
        total += (output_tokens / 1_000_000) * float(pricing["output_per_million"])
    if pricing.get("embedding_input_per_million") is not None:
        total += (input_tokens / 1_000_000) * float(pricing["embedding_input_per_million"])

    return round(total, 8)


def _pricing_for_model(*, provider: str, model: str) -> dict[str, float] | None:
    provider_key = "openai_compatible" if provider == "openai_compatible" else provider
    exact = MODEL_PRICING.get((provider_key, model))
    if exact:
        return exact

    for (pricing_provider, model_prefix), pricing in MODEL_PRICING.items():
        if pricing_provider != provider_key:
            continue
        if model.startswith(model_prefix):
            return pricing
    return None


def _extract_metric_int(metrics: dict[str, object], key: str) -> int | None:
    value = metrics.get(key)
    if isinstance(value, list) and value:
        value = value[-1]
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _round_optional(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 8)


MODEL_PRICING: dict[tuple[str, str], dict[str, float]] = {
    ("openai_compatible", "openai/gpt-5-mini"): {
        "input_per_million": 0.25,
        "output_per_million": 2.0,
    },
    ("openai_compatible", "anthropic/claude-sonnet-4"): {
        "input_per_million": 3.0,
        "output_per_million": 15.0,
    },
    ("openai_compatible", "google/gemini-2.5-pro"): {
        "input_per_million": 1.25,
        "output_per_million": 10.0,
    },
    ("openai_compatible", "text-embedding-3-small"): {
        "embedding_input_per_million": 0.02,
    },
    ("openai", "text-embedding-3-small"): {
        "embedding_input_per_million": 0.02,
    },
    ("openai", "text-embedding-3-large"): {
        "embedding_input_per_million": 0.13,
    },
}
