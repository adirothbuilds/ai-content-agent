from __future__ import annotations

import json
from pathlib import Path

from ai_content_agent.settings import get_settings


SUPPORTED_BENCHMARK_AGENTS = (
    "journal_assist",
    "idea_agent",
    "writer_agent",
    "seo_agent",
    "remix_agent",
)


def get_dataset_root(dataset_root: str | Path | None = None) -> Path:
    if dataset_root is not None:
        return Path(dataset_root)
    return Path(get_settings().benchmark_dataset_path)


def load_dataset(agent_key: str, dataset_root: str | Path | None = None) -> dict[str, object]:
    if agent_key not in SUPPORTED_BENCHMARK_AGENTS:
        supported = ", ".join(SUPPORTED_BENCHMARK_AGENTS)
        raise ValueError(f"Unsupported benchmark agent '{agent_key}'. Expected one of: {supported}.")

    path = get_dataset_root(dataset_root) / f"{agent_key}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    _validate_dataset(payload, agent_key, path)
    return payload


def list_dataset_agents(dataset_root: str | Path | None = None) -> list[str]:
    root = get_dataset_root(dataset_root)
    return sorted(path.stem for path in root.glob("*.json"))


def _validate_dataset(payload: dict[str, object], agent_key: str, path: Path) -> None:
    if payload.get("agent") != agent_key:
        raise ValueError(f"Dataset {path} has mismatched agent '{payload.get('agent')}'.")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"Dataset {path} must define a non-empty 'cases' list.")
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError(f"Dataset {path} contains a non-object case.")
        if not case.get("id") or not case.get("scenario"):
            raise ValueError(f"Dataset {path} has a case without 'id' or 'scenario'.")
