from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any
from uuid import uuid4

from ai_content_agent.agents.journal_assist import generate_journal_assist_draft
from ai_content_agent.agents.remix_agent import generate_remix_draft
from ai_content_agent.agents.seo_agent import generate_seo_revision
from ai_content_agent.agents.writer_agent import generate_writer_draft
from ai_content_agent.benchmarks.datasets import (
    SUPPORTED_BENCHMARK_AGENTS,
    load_dataset,
)
from ai_content_agent.benchmarks.validators import (
    all_terms_present,
    contains_forbidden_terms,
    distinct_ratio,
    keyword_coverage,
    looks_truncated,
    novelty_score,
    repetition_score,
)
from ai_content_agent.journal_sessions import JournalSession
from ai_content_agent.model_telemetry import clear_model_call_records, get_model_call_records
from ai_content_agent.services.idea_agent import generate_idea_candidates_from_context
from ai_content_agent.settings import get_settings


@dataclass(frozen=True)
class BenchmarkResult:
    run_id: str
    generated_at: str
    agents: dict[str, object]
    summary: dict[str, object]
    comparison: dict[str, object]


def run_benchmarks(
    *,
    agent_keys: list[str] | None = None,
    dataset_root: str | Path | None = None,
    output_root: str | Path | None = None,
    max_cases: int | None = None,
    report_only: bool = False,
) -> BenchmarkResult:
    settings = get_settings()
    selected_agents = agent_keys or list(SUPPORTED_BENCHMARK_AGENTS)
    benchmark_output_root = Path(output_root or settings.benchmark_output_path)

    previous_scored = _load_previous_scored_report(benchmark_output_root)
    if report_only:
        if not previous_scored:
            raise RuntimeError("No previous benchmark report found to render.")
        report_paths = write_benchmark_report(previous_scored, benchmark_output_root)
        return BenchmarkResult(
            run_id=str(previous_scored["run_id"]),
            generated_at=str(previous_scored["generated_at"]),
            agents=dict(previous_scored["agents"]),
            summary=dict(previous_scored["summary"]),
            comparison=dict(previous_scored.get("comparison", {})),
        )

    run_id = str(uuid4())
    generated_at = datetime.now(UTC).isoformat()
    effective_max_cases = max_cases if max_cases is not None else settings.benchmark_max_cases
    soft_budget = settings.benchmark_soft_budget_usd

    agents_payload: dict[str, object] = {}
    total_estimated_cost = 0.0
    budget_exhausted = False

    for agent_key in selected_agents:
        dataset = load_dataset(agent_key, dataset_root)
        cases = list(dataset["cases"])
        if effective_max_cases is not None:
            cases = cases[:effective_max_cases]

        case_results: list[dict[str, object]] = []
        for case in cases:
            if soft_budget is not None and total_estimated_cost >= soft_budget:
                budget_exhausted = True
                break
            case_result = _run_case(agent_key, case)
            case_results.append(case_result)
            total_estimated_cost += float(case_result["telemetry"]["estimated_cost_usd"])

        agent_summary = _summarize_agent_results(case_results)
        agents_payload[agent_key] = {
            "dataset_version": dataset["dataset_version"],
            "cases": case_results,
            "summary": agent_summary,
        }

    summary = _build_suite_summary(agents_payload, total_estimated_cost, budget_exhausted)
    comparison = _compare_with_previous(previous_scored, agents_payload)
    result = BenchmarkResult(
        run_id=run_id,
        generated_at=generated_at,
        agents=agents_payload,
        summary=summary,
        comparison=comparison,
    )
    _write_benchmark_artifacts(result, benchmark_output_root)
    return result


def write_benchmark_report(
    result: dict[str, object] | BenchmarkResult,
    output_root: str | Path | None = None,
) -> dict[str, Path]:
    settings = get_settings()
    benchmark_output_root = Path(output_root or settings.benchmark_output_path)
    payload = asdict(result) if isinstance(result, BenchmarkResult) else dict(result)
    generated_at = str(payload["generated_at"])
    timestamp = _timestamp_slug(generated_at)
    run_dir = benchmark_output_root / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    raw_path = run_dir / "raw.json"
    scored_path = run_dir / "scored.json"
    summary_path = run_dir / "summary.md"

    raw_payload = {
        "run_id": payload["run_id"],
        "generated_at": payload["generated_at"],
        "agents": payload["agents"],
    }
    raw_path.write_text(json.dumps(raw_payload, indent=2, ensure_ascii=True), encoding="utf-8")
    scored_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    summary_path.write_text(_render_markdown_summary(payload), encoding="utf-8")

    latest_dir = benchmark_output_root / "latest"
    latest_dir.mkdir(parents=True, exist_ok=True)
    (latest_dir / "raw.json").write_text(raw_path.read_text(encoding="utf-8"), encoding="utf-8")
    (latest_dir / "scored.json").write_text(
        scored_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (latest_dir / "summary.md").write_text(
        summary_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return {
        "run_dir": run_dir,
        "raw": raw_path,
        "scored": scored_path,
        "summary": summary_path,
    }


def _run_case(agent_key: str, case: dict[str, object]) -> dict[str, object]:
    clear_model_call_records()
    started_at = datetime.now(UTC)
    try:
        normalized_output = _execute_case(agent_key, case)
        validation = _score_case(agent_key, case, normalized_output, get_model_call_records())
        status = "passed"
        error = None
    except Exception as exc:
        normalized_output = None
        validation = {
            "quality_score": 0.0,
            "checks": {"execution_failed": False},
            "summary": f"{type(exc).__name__}: {exc}",
        }
        status = "failed"
        error = {"type": type(exc).__name__, "message": str(exc)}

    finished_at = datetime.now(UTC)
    records = get_model_call_records()
    telemetry = _summarize_telemetry(records)
    return {
        "case_id": case["id"],
        "scenario": case["scenario"],
        "tags": case.get("tags", []),
        "status": status,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "normalized_output": normalized_output,
        "validation": validation,
        "telemetry": telemetry,
        "execution_records": records,
        "error": error,
    }


def _execute_case(agent_key: str, case: dict[str, object]) -> dict[str, object]:
    if agent_key == "journal_assist":
        session = JournalSession(
            chat_id=int(case.get("chat_id", 999)),
            user_id=int(case.get("user_id", 111)),
            entries=dict(case["entries"]),
        )
        return generate_journal_assist_draft(session).model_dump()
    if agent_key == "idea_agent":
        return generate_idea_candidates_from_context(
            prompt=str(case["prompt"]),
            context_documents=list(case["context_documents"]),
            history_evaluator=lambda candidates: [
                {"has_similar_history": False, "matches": []} for _ in candidates
            ],
        )
    if agent_key == "writer_agent":
        return generate_writer_draft(
            idea=dict(case["idea"]),
            context_documents=list(case["context_documents"]),
        )
    if agent_key == "seo_agent":
        return generate_seo_revision(str(case["draft"]))
    if agent_key == "remix_agent":
        return generate_remix_draft(
            draft=str(case["draft"]),
            feedback=str(case["feedback"]),
        )
    raise ValueError(f"Unsupported benchmark agent '{agent_key}'.")


def _score_case(
    agent_key: str,
    case: dict[str, object],
    normalized_output: dict[str, object],
    records: list[dict[str, object]],
) -> dict[str, object]:
    if agent_key == "journal_assist":
        return _score_journal_assist_case(case, normalized_output, records)
    if agent_key == "idea_agent":
        return _score_idea_agent_case(case, normalized_output, records)
    if agent_key == "writer_agent":
        return _score_writer_agent_case(case, normalized_output, records)
    if agent_key == "seo_agent":
        return _score_seo_agent_case(case, normalized_output, records)
    if agent_key == "remix_agent":
        return _score_remix_agent_case(case, normalized_output, records)
    raise ValueError(f"Unsupported benchmark agent '{agent_key}'.")


def _score_journal_assist_case(
    case: dict[str, object],
    normalized_output: dict[str, object],
    records: list[dict[str, object]],
) -> dict[str, object]:
    scoring = dict(case.get("scoring", {}))
    combined = " ".join(
        str(normalized_output.get(field, ""))
        for field in (
            "work_summary",
            "problem_solved",
            "tools_used",
            "lesson_learned",
            "outcome",
            "why_it_matters",
        )
    )
    checks = {
        "all_fields_present": all(bool(normalized_output.get(field)) for field in (
            "work_summary",
            "problem_solved",
            "tools_used",
            "lesson_learned",
            "outcome",
            "why_it_matters",
        )),
        "required_terms_coverage": keyword_coverage(combined, list(scoring.get("required_terms", []))),
        "forbidden_terms_absent": not contains_forbidden_terms(
            combined,
            list(scoring.get("forbidden_terms", [])),
        ),
        "gaps_present": bool(normalized_output.get("gaps")) if scoring.get("expect_gaps") else True,
        "structured_output_observed": _structured_output_observed(records),
    }
    quality_score = round(
        mean(
            [
                1.0 if checks["all_fields_present"] else 0.0,
                float(checks["required_terms_coverage"]),
                1.0 if checks["forbidden_terms_absent"] else 0.0,
                1.0 if checks["gaps_present"] else 0.0,
                1.0 if checks["structured_output_observed"] else 0.0,
            ]
        ),
        4,
    )
    return {"quality_score": quality_score, "checks": checks, "summary": "Journal Assist benchmark scored."}


def _score_idea_agent_case(
    case: dict[str, object],
    normalized_output: dict[str, object],
    records: list[dict[str, object]],
) -> dict[str, object]:
    ideas = list(normalized_output["ideas"])
    context_ids = {str(document["document_id"]) for document in case["context_documents"]}
    titles = [str(idea["title"]) for idea in ideas]
    angles = [str(idea["angle"]) for idea in ideas]
    combined_ideas = [
        "\n".join([str(idea["title"]), str(idea["angle"]), str(idea["summary"])]) for idea in ideas
    ]
    historical_topics = list(case.get("historical_topics", []))
    checks = {
        "exactly_three_ideas": len(ideas) == 3,
        "grounded_source_ids": all(
            set(map(str, idea["source_document_ids"])).issubset(context_ids) and idea["source_document_ids"]
            for idea in ideas
        ),
        "title_distinctness": distinct_ratio(titles),
        "angle_distinctness": distinct_ratio(angles),
        "novelty_score": novelty_score(combined_ideas, historical_topics),
        "structured_output_observed": _structured_output_observed(records),
    }
    quality_score = round(
        mean(
            [
                1.0 if checks["exactly_three_ideas"] else 0.0,
                1.0 if checks["grounded_source_ids"] else 0.0,
                float(checks["title_distinctness"]),
                float(checks["angle_distinctness"]),
                float(checks["novelty_score"]),
                1.0 if checks["structured_output_observed"] else 0.0,
            ]
        ),
        4,
    )
    return {"quality_score": quality_score, "checks": checks, "summary": "Idea Agent benchmark scored."}


def _score_writer_agent_case(
    case: dict[str, object],
    normalized_output: dict[str, object],
    records: list[dict[str, object]],
) -> dict[str, object]:
    scoring = dict(case.get("scoring", {}))
    draft = str(normalized_output["draft"])
    context_ids = {str(document["document_id"]) for document in case["context_documents"]}
    checks = {
        "valid_source_ids": set(map(str, normalized_output["source_document_ids"])).issubset(context_ids),
        "required_terms_coverage": keyword_coverage(draft, list(scoring.get("required_terms", []))),
        "forbidden_terms_absent": not contains_forbidden_terms(
            draft,
            list(scoring.get("forbidden_terms", [])),
        ),
        "not_truncated": not looks_truncated(draft),
        "repetition_score": repetition_score(draft),
        "structured_output_observed": _structured_output_observed(records),
        "fallback_used": _fallback_used(records),
    }
    quality_score = round(
        mean(
            [
                1.0 if checks["valid_source_ids"] else 0.0,
                float(checks["required_terms_coverage"]),
                1.0 if checks["forbidden_terms_absent"] else 0.0,
                1.0 if checks["not_truncated"] else 0.0,
                float(checks["repetition_score"]),
            ]
        ),
        4,
    )
    return {"quality_score": quality_score, "checks": checks, "summary": "Writer Agent benchmark scored."}


def _score_seo_agent_case(
    case: dict[str, object],
    normalized_output: dict[str, object],
    records: list[dict[str, object]],
) -> dict[str, object]:
    scoring = dict(case.get("scoring", {}))
    draft = str(normalized_output["draft"])
    hashtags = [str(tag) for tag in normalized_output["hashtags"]]
    required_hashtags = [str(tag) for tag in scoring.get("required_hashtags", [])]
    checks = {
        "hashtags_present": bool(hashtags),
        "required_hashtags_present": all_terms_present(" ".join(hashtags), required_hashtags),
        "preserve_terms": all_terms_present(draft, list(scoring.get("preserve_terms", []))),
        "forbidden_terms_absent": not contains_forbidden_terms(
            draft,
            list(scoring.get("forbidden_terms", [])),
        ),
        "not_truncated": not looks_truncated(draft),
        "structured_output_observed": _structured_output_observed(records),
        "fallback_used": _fallback_used(records),
    }
    quality_score = round(
        mean(
            [
                1.0 if checks["hashtags_present"] else 0.0,
                1.0 if checks["required_hashtags_present"] else 0.0,
                1.0 if checks["preserve_terms"] else 0.0,
                1.0 if checks["forbidden_terms_absent"] else 0.0,
                1.0 if checks["not_truncated"] else 0.0,
            ]
        ),
        4,
    )
    return {"quality_score": quality_score, "checks": checks, "summary": "SEO Agent benchmark scored."}


def _score_remix_agent_case(
    case: dict[str, object],
    normalized_output: dict[str, object],
    records: list[dict[str, object]],
) -> dict[str, object]:
    scoring = dict(case.get("scoring", {}))
    original_draft = str(case["draft"])
    remixed_draft = str(normalized_output["draft"])
    checks = {
        "draft_changed": normalize_bool(remixed_draft != original_draft),
        "preserve_terms": all_terms_present(remixed_draft, list(scoring.get("preserve_terms", []))),
        "required_terms_coverage": keyword_coverage(
            remixed_draft,
            list(scoring.get("required_terms", [])),
        ),
        "not_truncated": not looks_truncated(remixed_draft),
        "shorter_when_requested": len(remixed_draft) <= len(original_draft)
        if scoring.get("should_reduce_length")
        else True,
        "structured_output_observed": _structured_output_observed(records),
        "fallback_used": _fallback_used(records),
    }
    quality_score = round(
        mean(
            [
                1.0 if checks["draft_changed"] else 0.0,
                1.0 if checks["preserve_terms"] else 0.0,
                float(checks["required_terms_coverage"]),
                1.0 if checks["not_truncated"] else 0.0,
                1.0 if checks["shorter_when_requested"] else 0.0,
            ]
        ),
        4,
    )
    return {"quality_score": quality_score, "checks": checks, "summary": "Remix Agent benchmark scored."}


def _summarize_telemetry(records: list[dict[str, object]]) -> dict[str, object]:
    estimated_cost = round(sum(float(record.get("estimated_cost_usd") or 0.0) for record in records), 8)
    llm_records = [record for record in records if record["call_type"] == "llm"]
    return {
        "record_count": len(records),
        "structured_output_expected_count": sum(
            1 for record in llm_records if record.get("structured_output_expected")
        ),
        "structured_output_observed_count": sum(
            1 for record in llm_records if record.get("structured_output_observed") is True
        ),
        "fallback_count": sum(1 for record in llm_records if record.get("fallback_used")),
        "latency_ms": round(sum(float(record.get("duration_ms") or 0.0) for record in records), 2),
        "input_tokens": sum(int(record["usage"].get("input_tokens") or 0) for record in records),
        "output_tokens": sum(int(record["usage"].get("output_tokens") or 0) for record in records),
        "reasoning_tokens": sum(int(record["usage"].get("reasoning_tokens") or 0) for record in records),
        "estimated_cost_usd": estimated_cost,
    }


def _summarize_agent_results(case_results: list[dict[str, object]]) -> dict[str, object]:
    if not case_results:
        return {
            "case_count": 0,
            "pass_rate": 0.0,
            "average_quality_score": 0.0,
            "average_latency_ms": 0.0,
            "total_estimated_cost_usd": 0.0,
            "fallback_rate": 0.0,
            "structured_output_adherence_rate": 0.0,
        }

    pass_rate = mean(1.0 if case["status"] == "passed" else 0.0 for case in case_results)
    average_quality = mean(float(case["validation"]["quality_score"]) for case in case_results)
    average_latency = mean(float(case["telemetry"]["latency_ms"]) for case in case_results)
    total_cost = sum(float(case["telemetry"]["estimated_cost_usd"]) for case in case_results)
    fallback_rate = mean(
        (
            float(case["telemetry"]["fallback_count"])
            / max(1, int(case["telemetry"]["structured_output_expected_count"]))
        )
        for case in case_results
    )
    adherence_rate = mean(
        (
            float(case["telemetry"]["structured_output_observed_count"])
            / max(1, int(case["telemetry"]["structured_output_expected_count"]))
        )
        for case in case_results
    )
    return {
        "case_count": len(case_results),
        "pass_rate": round(pass_rate, 4),
        "average_quality_score": round(average_quality, 4),
        "average_latency_ms": round(average_latency, 2),
        "total_estimated_cost_usd": round(total_cost, 8),
        "fallback_rate": round(fallback_rate, 4),
        "structured_output_adherence_rate": round(adherence_rate, 4),
    }


def _build_suite_summary(
    agents_payload: dict[str, object],
    total_estimated_cost: float,
    budget_exhausted: bool,
) -> dict[str, object]:
    all_case_results = [
        case
        for agent in agents_payload.values()
        for case in agent["cases"]
    ]
    return {
        "agent_count": len(agents_payload),
        "case_count": len(all_case_results),
        "average_quality_score": round(
            mean(float(case["validation"]["quality_score"]) for case in all_case_results),
            4,
        )
        if all_case_results
        else 0.0,
        "total_estimated_cost_usd": round(total_estimated_cost, 8),
        "budget_exhausted": budget_exhausted,
    }


def _compare_with_previous(
    previous_scored: dict[str, object] | None,
    agents_payload: dict[str, object],
) -> dict[str, object]:
    if not previous_scored:
        return {}

    comparison: dict[str, object] = {}
    previous_agents = previous_scored.get("agents", {})
    for agent_key, payload in agents_payload.items():
        previous_summary = (
            previous_agents.get(agent_key, {}).get("summary", {})
            if isinstance(previous_agents, dict)
            else {}
        )
        current_summary = payload["summary"]
        comparison[agent_key] = {
            "quality_score_delta": round(
                float(current_summary["average_quality_score"])
                - float(previous_summary.get("average_quality_score", 0.0)),
                4,
            ),
            "latency_ms_delta": round(
                float(current_summary["average_latency_ms"])
                - float(previous_summary.get("average_latency_ms", 0.0)),
                2,
            ),
            "cost_usd_delta": round(
                float(current_summary["total_estimated_cost_usd"])
                - float(previous_summary.get("total_estimated_cost_usd", 0.0)),
                8,
            ),
            "fallback_rate_delta": round(
                float(current_summary["fallback_rate"])
                - float(previous_summary.get("fallback_rate", 0.0)),
                4,
            ),
        }
    return comparison


def _write_benchmark_artifacts(result: BenchmarkResult, output_root: Path) -> None:
    write_benchmark_report(result, output_root)


def _load_previous_scored_report(output_root: Path) -> dict[str, object] | None:
    latest_scored = output_root / "latest" / "scored.json"
    if not latest_scored.is_file():
        return None
    return json.loads(latest_scored.read_text(encoding="utf-8"))


def _render_markdown_summary(payload: dict[str, object]) -> str:
    lines = [
        "# Benchmark Summary",
        "",
        f"- Run ID: `{payload['run_id']}`",
        f"- Generated At: `{payload['generated_at']}`",
        f"- Total Estimated Cost: `${payload['summary']['total_estimated_cost_usd']}`",
        "",
        "## Quality",
        "",
        "| Agent | Cases | Pass Rate | Avg Quality | Fallback Rate | Structured Adherence |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for agent_key, agent_payload in payload["agents"].items():
        summary = agent_payload["summary"]
        lines.append(
            f"| {agent_key} | {summary['case_count']} | {summary['pass_rate']:.2f} | "
            f"{summary['average_quality_score']:.2f} | {summary['fallback_rate']:.2f} | "
            f"{summary['structured_output_adherence_rate']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Latency And Cost",
            "",
            "| Agent | Avg Latency (ms) | Total Cost (USD) |",
            "| --- | ---: | ---: |",
        ]
    )
    for agent_key, agent_payload in payload["agents"].items():
        summary = agent_payload["summary"]
        lines.append(
            f"| {agent_key} | {summary['average_latency_ms']:.2f} | {summary['total_estimated_cost_usd']:.8f} |"
        )

    lines.extend(
        [
            "",
            "## Case Failures",
            "",
        ]
    )
    failure_count = 0
    for agent_key, agent_payload in payload["agents"].items():
        for case in agent_payload["cases"]:
            if case["status"] == "passed" and float(case["validation"]["quality_score"]) >= 0.7:
                continue
            failure_count += 1
            lines.append(
                f"- `{agent_key}:{case['case_id']}` status=`{case['status']}` quality=`{case['validation']['quality_score']}` summary={case['validation']['summary']}"
            )
    if failure_count == 0:
        lines.append("- No failing or low-quality cases detected.")

    if payload.get("comparison"):
        lines.extend(["", "## Comparison To Previous Run", ""])
        lines.append("| Agent | Quality Delta | Latency Delta (ms) | Cost Delta (USD) | Fallback Delta |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for agent_key, comparison in payload["comparison"].items():
            lines.append(
                f"| {agent_key} | {comparison['quality_score_delta']:+.4f} | "
                f"{comparison['latency_ms_delta']:+.2f} | {comparison['cost_usd_delta']:+.8f} | "
                f"{comparison['fallback_rate_delta']:+.4f} |"
            )

    return "\n".join(lines) + "\n"


def _timestamp_slug(timestamp: str) -> str:
    return timestamp.replace(":", "-").replace("+00:00", "Z")


def _structured_output_observed(records: list[dict[str, object]]) -> bool:
    llm_records = [record for record in records if record["call_type"] == "llm"]
    return bool(llm_records) and all(
        record.get("structured_output_observed") is True for record in llm_records
    )


def _fallback_used(records: list[dict[str, object]]) -> bool:
    return any(record.get("fallback_used") for record in records if record["call_type"] == "llm")


def normalize_bool(value: bool) -> bool:
    return bool(value)
