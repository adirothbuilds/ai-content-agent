from __future__ import annotations

import json
import os
import traceback
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_content_agent.benchmarks.validators import looks_truncated
from ai_content_agent.agents.journal_assist import generate_journal_assist_draft
from ai_content_agent.agents.remix_agent import generate_remix_draft
from ai_content_agent.agents.seo_agent import generate_seo_revision
from ai_content_agent.agents.writer_agent import generate_writer_draft
from ai_content_agent.embeddings import build_embedding_vector, set_embedder
from ai_content_agent.journal_sessions import JournalSession
from ai_content_agent.llm import LlmTask, resolve_task_config
from ai_content_agent.model_telemetry import clear_model_call_records, get_model_call_records
from ai_content_agent.prompts import (
    IDEA_AGENT_PROMPT,
    JOURNAL_ASSIST_PROMPT,
    REMIX_AGENT_PROMPT,
    SEO_AGENT_PROMPT,
    WRITER_AGENT_PROMPT,
)
from ai_content_agent.services.idea_agent import generate_idea_candidates
from ai_content_agent.settings import get_settings


REPORT_PATH = Path(os.getenv("LIVE_AI_REPORT_PATH", "reports/live_ai/latest.json"))


def _require_live_ai() -> None:
    if os.getenv("RUN_LIVE_AI_TESTS", "").lower() != "true":
        pytest.skip("Set RUN_LIVE_AI_TESTS=true to run live AI smoke tests.")


@pytest.mark.live_ai
def test_live_ai_full_smoke(monkeypatch) -> None:
    _require_live_ai()
    set_embedder(None)
    clear_model_call_records()

    report: dict[str, object] = {
        "status": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "report_version": 1,
        "settings": {},
        "steps": {},
    }

    try:
        settings = get_settings()
        report["settings"] = {
            "tasks": {
                task.value: asdict(resolve_task_config(task, settings))
                for task in LlmTask
            },
            "embedding": {
                "provider": settings.embedding_provider,
                "model": settings.embedding_model,
            },
            "prompt_versions": {
                "journal_assist": JOURNAL_ASSIST_PROMPT.version,
                "idea_agent": IDEA_AGENT_PROMPT.version,
                "writer_agent": WRITER_AGENT_PROMPT.version,
                "seo_agent": SEO_AGENT_PROMPT.version,
                "remix_agent": REMIX_AGENT_PROMPT.version,
            },
        }

        journal_session = JournalSession(
            chat_id=999,
            user_id=111,
            entries={
                "work_summary": "Built a Telegram-first publish workflow that stores journal entries, drafts, and post history in MongoDB.",
                "problem_solved": "The earlier flow stopped before publish and gave no durable record for anti-duplication or history review.",
            },
        )

        context_documents = [
            {
                "document_id": "journal-live-1",
                "document_type": "journal_entry",
                "content": (
                    "Worked on a Telegram-first workflow that moves from journal capture "
                    "to idea generation, drafting, remix, and publish."
                ),
                "score": 0.92,
            },
            {
                "document_id": "github-live-1",
                "document_type": "github_activity",
                "content": (
                    "Commit: persist post history and publish checkpoints so future ideas "
                    "can avoid repeated angles."
                ),
                "score": 0.87,
            },
        ]

        monkeypatch.setattr(
            "ai_content_agent.services.idea_agent.retrieve_documents",
            lambda **_: context_documents,
        )
        monkeypatch.setattr(
            "ai_content_agent.services.idea_agent.evaluate_idea_candidates",
            lambda candidates: [
                {"candidate": candidate, "has_similar_history": False, "matches": []}
                for candidate in candidates
            ],
        )

        embedding_vector = _run_step(
            report["steps"],
            "embedding",
            lambda: build_embedding_vector(
                "Live smoke test for embeddings in the AI content workflow."
            ),
            serializer=lambda vector: {
                "dimensions": len(vector),
                "preview": [round(value, 6) for value in vector[:8]],
            },
        )

        journal_draft = _run_step(
            report["steps"],
            "journal_assist",
            lambda: generate_journal_assist_draft(journal_session),
            serializer=lambda draft: draft.model_dump(),
        )

        idea_result = _run_step(
            report["steps"],
            "idea_agent",
            lambda: generate_idea_candidates(
                prompt="Generate grounded LinkedIn ideas from this publish workflow work."
            ),
            serializer=lambda result: {
                "ideas": result["ideas"],
                "llm": result["llm"],
                "context_document_ids": [
                    document["document_id"] for document in result["context_documents"]
                ],
            },
        )

        selected_idea = idea_result["ideas"][0]

        writer_result = _run_step(
            report["steps"],
            "writer_agent",
            lambda: generate_writer_draft(
                idea=selected_idea,
                context_documents=context_documents,
            ),
        )

        seo_result = _run_step(
            report["steps"],
            "seo_agent",
            lambda: generate_seo_revision(writer_result["draft"]),
        )

        remix_result = _run_step(
            report["steps"],
            "remix_agent",
            lambda: generate_remix_draft(
                draft=seo_result["draft"],
                feedback="Make the opening sharper and slightly more practical.",
            ),
        )

        assert embedding_vector, "Embedding vector should not be empty."
        assert journal_draft.work_summary
        assert len(idea_result["ideas"]) == 3
        assert writer_result["source_document_ids"]
        assert seo_result["hashtags"]
        assert remix_result["draft"]
        assert not looks_truncated(writer_result["draft"])
        assert not looks_truncated(seo_result["draft"])
        assert not looks_truncated(remix_result["draft"])

        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        raise
    finally:
        report["model_calls"] = get_model_call_records()
        report["estimated_total_cost_usd"] = round(
            sum(float(record.get("estimated_cost_usd") or 0.0) for record in report["model_calls"]),
            8,
        )
        report["finished_at"] = datetime.now(UTC).isoformat()
        _write_report(report)
        set_embedder(None)
        clear_model_call_records()


def _run_step(
    steps: dict[str, object],
    name: str,
    func,
    serializer=None,
):
    record_start = len(get_model_call_records())
    try:
        result = func()
    except Exception as exc:
        step_records = get_model_call_records()[record_start:]
        steps[name] = {
            "status": "failed",
            "duration_ms": round(
                sum(float(record.get("duration_ms") or 0.0) for record in step_records),
                2,
            ),
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
            "execution_records": step_records,
            "telemetry": _summarize_step_records(step_records),
        }
        raise

    step_records = get_model_call_records()[record_start:]
    steps[name] = {
        "status": "passed",
        "duration_ms": round(
            sum(float(record.get("duration_ms") or 0.0) for record in step_records),
            2,
        ),
        "result": serializer(result) if serializer else result,
        "execution_records": step_records,
        "telemetry": _summarize_step_records(step_records),
    }
    return result


def _write_report(report: dict[str, object]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")


def _summarize_step_records(records: list[dict[str, object]]) -> dict[str, object]:
    llm_records = [record for record in records if record["call_type"] == "llm"]
    return {
        "fallback_used": any(record.get("fallback_used") for record in llm_records),
        "structured_output_expected": any(
            record.get("structured_output_expected") for record in llm_records
        ),
        "structured_output_observed": all(
            record.get("structured_output_observed") is True for record in llm_records
        )
        if llm_records
        else False,
        "estimated_cost_usd": round(
            sum(float(record.get("estimated_cost_usd") or 0.0) for record in records),
            8,
        ),
    }
