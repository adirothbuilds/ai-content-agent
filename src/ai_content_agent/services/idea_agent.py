from __future__ import annotations

from dataclasses import asdict, dataclass

from pydantic import BaseModel, Field

from ai_content_agent.agents.runtime import build_agno_agent, run_agent
from ai_content_agent.llm import LlmTask
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

    agent = build_agno_agent(
        task=LlmTask.IDEA,
        instructions=[
            "Generate distinct LinkedIn post ideas grounded in the provided source context.",
            f"Return exactly {IDEA_AGENT_CANDIDATE_COUNT} ideas.",
            "Each idea must cite one or more provided source document IDs.",
            "Do not invent source IDs or unsupported facts.",
        ],
        response_model=IdeaBatch,
    )
    result = run_agent(agent, _build_prompt(prompt, context_documents))
    parsed_candidates = _parse_candidates(result.content, context_documents)
    ranked_candidates = _apply_post_history_ranking(parsed_candidates)

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
        },
    }


def _build_prompt(
    prompt: str,
    context_documents: list[dict[str, object]],
) -> str:
    blocks = [f"User prompt: {prompt}", "Context documents:"]
    for document in context_documents:
        blocks.append(
            "\n".join(
                [
                    f"ID: {document['document_id']}",
                    f"Type: {document['document_type']}",
                    f"Score: {document['score']}",
                    f"Content: {document['content']}",
                ]
            )
        )
    return "\n\n".join(blocks)


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
) -> list[IdeaCandidate]:
    evaluations = evaluate_idea_candidates(
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
