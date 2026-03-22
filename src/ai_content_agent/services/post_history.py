from collections.abc import Sequence

from ai_content_agent.services.retrieval import retrieve_documents
from ai_content_agent.settings import get_settings


def find_similar_post_history(
    *,
    candidate_text: str,
    top_k: int | None = None,
) -> list[dict[str, object]]:
    settings = get_settings()
    results = retrieve_documents(
        query=candidate_text,
        collections=["post_history"],
        top_k=top_k or settings.retrieval_top_k,
    )
    return [
        result
        for result in results
        if float(result["score"]) >= settings.post_history_similarity_threshold
    ]


def evaluate_idea_candidates(
    candidates: Sequence[str],
) -> list[dict[str, object]]:
    evaluations = []
    for candidate in candidates:
        matches = find_similar_post_history(candidate_text=candidate)
        evaluations.append(
            {
                "candidate": candidate,
                "has_similar_history": bool(matches),
                "matches": matches,
            }
        )
    return evaluations


def evaluate_draft_candidate(draft_text: str) -> dict[str, object]:
    matches = find_similar_post_history(candidate_text=draft_text)
    return {
        "candidate": draft_text,
        "has_similar_history": bool(matches),
        "matches": matches,
    }
