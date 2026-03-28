from __future__ import annotations

import re
from collections import Counter


_TRUNCATED_ENDINGS = (
    " or",
    " and",
    " but",
    " with",
    " because",
    " so",
    " then",
    " failed",
    " failed or",
    " could",
)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def tokenize(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", normalize_text(value)) if len(token) > 2}


def keyword_coverage(value: str, required_terms: list[str]) -> float:
    if not required_terms:
        return 1.0
    haystack = normalize_text(value)
    matched = sum(1 for term in required_terms if normalize_text(term) in haystack)
    return round(matched / len(required_terms), 4)


def contains_forbidden_terms(value: str, forbidden_terms: list[str]) -> bool:
    haystack = normalize_text(value)
    return any(normalize_text(term) in haystack for term in forbidden_terms)


def all_terms_present(value: str, terms: list[str]) -> bool:
    haystack = normalize_text(value)
    return all(normalize_text(term) in haystack for term in terms)


def looks_truncated(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return True
    if stripped.endswith((":", ",", ";", "-", "—", "(", "/", "→")):
        return True
    normalized = normalize_text(stripped)
    if any(normalized.endswith(ending) for ending in _TRUNCATED_ENDINGS):
        return True
    return False


def distinct_ratio(values: list[str]) -> float:
    if not values:
        return 1.0
    normalized = [normalize_text(value) for value in values]
    return round(len(set(normalized)) / len(normalized), 4)


def novelty_score(values: list[str], historical_topics: list[str]) -> float:
    if not values or not historical_topics:
        return 1.0
    topic_tokens = [tokenize(topic) for topic in historical_topics]
    per_value_scores: list[float] = []
    for value in values:
        value_tokens = tokenize(value)
        if not value_tokens:
            per_value_scores.append(0.0)
            continue
        max_overlap = 0.0
        for historical in topic_tokens:
            overlap = len(value_tokens & historical) / max(1, len(value_tokens | historical))
            max_overlap = max(max_overlap, overlap)
        per_value_scores.append(max(0.0, 1 - max_overlap))
    return round(sum(per_value_scores) / len(per_value_scores), 4)


def repetition_score(value: str) -> float:
    tokens = re.findall(r"[a-z0-9]+", normalize_text(value))
    if not tokens:
        return 0.0
    counts = Counter(tokens)
    repeated = sum(count - 1 for count in counts.values() if count > 1)
    penalty = repeated / len(tokens)
    return round(max(0.0, 1 - penalty), 4)
