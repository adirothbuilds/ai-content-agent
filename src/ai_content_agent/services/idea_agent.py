from __future__ import annotations

from dataclasses import asdict, dataclass

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import (
    build_agno_agent,
    coerce_response_model_output,
    run_agent,
)
from ai_content_agent.llm import LlmTask, resolve_task_config
from ai_content_agent.model_telemetry import update_model_call_record
from ai_content_agent.prompts import IDEA_AGENT_PROMPT, build_idea_agent_prompt
from ai_content_agent.services.post_history import evaluate_idea_candidates
from ai_content_agent.services.retrieval import retrieve_documents


IDEA_AGENT_COLLECTIONS = ("journal_entries", "github_activity")
IDEA_AGENT_CANDIDATE_COUNT = 5
IDEA_AGENT_FINAL_COUNT = 3


class IdeaAgentError(RuntimeError):
    pass


class IdeaDraft(BaseModel):
    title: str = Field(min_length=1)
    angle: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    source_document_ids: list[str] = Field(min_length=1)


class IdeaBatch(BaseModel):
    ideas: list[IdeaDraft] = Field(min_length=IDEA_AGENT_CANDIDATE_COUNT)


@dataclass(frozen=True)
class IdeaCandidate:
    title: str
    angle: str
    summary: str
    source_document_ids: list[str]
    has_similar_history: bool
    duplicate_matches: list[dict[str, object]]


def generate_idea_candidates(
    *,
    prompt: str,
    retrieval_top_k: int | None = None,
) -> dict[str, object]:
    context_documents = retrieve_documents(
        query=prompt,
        collections=IDEA_AGENT_COLLECTIONS,
        top_k=retrieval_top_k,
    )
    if not context_documents:
        raise IdeaAgentError("Idea Agent requires retrieved journal or GitHub context.")

    return generate_idea_candidates_from_context(
        prompt=prompt,
        context_documents=context_documents,
    )


def generate_idea_candidates_from_context(
    *,
    prompt: str,
    context_documents: list[dict[str, object]],
    history_evaluator=None,
) -> dict[str, object]:
    if not context_documents:
        raise IdeaAgentError("Idea Agent requires retrieved journal or GitHub context.")
    resolved_history_evaluator = history_evaluator or evaluate_idea_candidates

    agent = build_agno_agent(
        task=LlmTask.IDEA,
        instructions=list(IDEA_AGENT_PROMPT.instructions),
        response_model=IdeaBatch,
    )
    task_config = resolve_task_config(LlmTask.IDEA)
    result = run_agent(
        agent,
        build_idea_agent_prompt(
            user_prompt=prompt,
            requested_count=IDEA_AGENT_CANDIDATE_COUNT,
            context_documents=context_documents,
        ),
        task=LlmTask.IDEA,
        provider=task_config.provider.value,
        model=task_config.model,
        prompt_version=IDEA_AGENT_PROMPT.version,
        structured_output_expected=True,
    )
    parsed_candidates = _parse_candidates(
        coerce_response_model_output(result.content, IdeaBatch),
        context_documents,
    )
    if getattr(result, "record_id", None):
        update_model_call_record(
            result.record_id,
            structured_output_observed=True,
            fallback_used=False,
        )
    ranked_candidates = _apply_post_history_ranking(
        parsed_candidates,
        history_evaluator=resolved_history_evaluator,
    )

    if len(ranked_candidates) < IDEA_AGENT_FINAL_COUNT:
        raise IdeaAgentError("Idea Agent could not produce three grounded ideas.")

    return {
        "ideas": [
            asdict(candidate) for candidate in ranked_candidates[:IDEA_AGENT_FINAL_COUNT]
        ],
        "context_documents": context_documents,
        "llm": {
            "model": result.model,
            "metrics": result.metrics,
            "prompt_version": IDEA_AGENT_PROMPT.version,
        },
    }


def _parse_candidates(
    batch: IdeaBatch,
    context_documents: list[dict[str, object]],
) -> list[IdeaCandidate]:
    valid_ids = {
        str(document["document_id"])
        for document in context_documents
        if document.get("document_id")
    }
    candidates: list[IdeaCandidate] = []
    for item in batch.ideas:
        source_document_ids = [
            str(value) for value in item.source_document_ids if str(value) in valid_ids
        ]
        if not source_document_ids:
            continue
        candidates.append(
            IdeaCandidate(
                title=item.title,
                angle=item.angle,
                summary=item.summary,
                source_document_ids=source_document_ids,
                has_similar_history=False,
                duplicate_matches=[],
            )
        )
    return _deduplicate_candidates(candidates)


def _deduplicate_candidates(
    candidates: list[IdeaCandidate],
) -> list[IdeaCandidate]:
    seen_keys: set[tuple[str, str]] = set()
    unique_candidates: list[IdeaCandidate] = []
    for candidate in candidates:
        key = (
            candidate.title.strip().lower(),
            candidate.angle.strip().lower(),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_candidates.append(candidate)
    return unique_candidates


def _apply_post_history_ranking(
    candidates: list[IdeaCandidate],
    *,
    history_evaluator=None,
) -> list[IdeaCandidate]:
    resolved_history_evaluator = history_evaluator or evaluate_idea_candidates
    evaluations = resolved_history_evaluator(
        [
            "\n".join([candidate.title, candidate.angle, candidate.summary])
            for candidate in candidates
        ]
    )
    ranked_candidates: list[IdeaCandidate] = []
    for candidate, evaluation in zip(candidates, evaluations, strict=True):
        ranked_candidates.append(
            IdeaCandidate(
                title=candidate.title,
                angle=candidate.angle,
                summary=candidate.summary,
                source_document_ids=candidate.source_document_ids,
                has_similar_history=bool(evaluation["has_similar_history"]),
                duplicate_matches=list(evaluation["matches"]),
            )
        )
    ranked_candidates.sort(
        key=lambda candidate: (
            candidate.has_similar_history,
            -len(candidate.source_document_ids),
            candidate.title.lower(),
        )
    )
    return ranked_candidates
