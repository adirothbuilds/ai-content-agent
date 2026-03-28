import json
from pathlib import Path

from ai_content_agent.benchmarks.datasets import load_dataset
from ai_content_agent.benchmarks.runner import run_benchmarks
from ai_content_agent.settings import reset_settings_cache


ENVIRONMENT = {
    "APP_ENV": "test",
    "APP_HOST": "127.0.0.1",
    "APP_PORT": "8000",
    "MONGODB_URI": "mongodb://localhost:27017",
    "MONGODB_DATABASE": "ai_content_agent",
    "TELEGRAM_BOT_TOKEN": "telegram-token",
    "PUBLIC_BASE_URL": "https://example.com",
    "CLOUDFLARED_TUNNEL_TOKEN": "cloudflare-token",
    "GITHUB_TOKEN": "github-token",
    "GITHUB_USERNAME": "adiroth",
    "OPENAI_API_KEY": "",
    "OPENAI_COMPATIBLE_API_KEY": "router-key",
    "OPENAI_COMPATIBLE_BASE_URL": "https://openrouter.ai/api/v1",
    "GEMINI_API_KEY": "",
    "ANTHROPIC_API_KEY": "",
    "IDEA_PROVIDER": "openai_compatible",
    "IDEA_MODEL": "openai/gpt-5-mini",
    "JOURNAL_ASSIST_PROVIDER": "openai_compatible",
    "JOURNAL_ASSIST_MODEL": "openai/gpt-5-mini",
    "SEO_PROVIDER": "openai_compatible",
    "SEO_MODEL": "google/gemini-2.5-pro",
    "WRITER_PROVIDER": "openai_compatible",
    "WRITER_MODEL": "anthropic/claude-sonnet-4",
    "REMIX_PROVIDER": "openai_compatible",
    "REMIX_MODEL": "anthropic/claude-sonnet-4",
    "EMBEDDING_PROVIDER": "openai_compatible",
    "EMBEDDING_MODEL": "text-embedding-3-small",
    "BENCHMARK_OUTPUT_PATH": "./reports/benchmarks",
}


def _set_environment(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()


def test_load_dataset_reads_checked_in_fixture() -> None:
    dataset = load_dataset("journal_assist")

    assert dataset["agent"] == "journal_assist"
    assert dataset["dataset_version"] == "v1"
    assert dataset["cases"]


def test_run_benchmarks_writes_raw_scored_and_markdown(monkeypatch, tmp_path) -> None:
    _set_environment(monkeypatch)

    monkeypatch.setattr(
        "ai_content_agent.benchmarks.runner._run_case",
        lambda agent_key, case: {
            "case_id": case["id"],
            "scenario": case["scenario"],
            "tags": case.get("tags", []),
            "status": "passed",
            "started_at": "2026-03-22T00:00:00+00:00",
            "finished_at": "2026-03-22T00:00:01+00:00",
            "normalized_output": {"ok": True},
            "validation": {
                "quality_score": 0.8,
                "checks": {"dummy": True},
                "summary": "Scored.",
            },
            "telemetry": {
                "record_count": 1,
                "structured_output_expected_count": 1,
                "structured_output_observed_count": 1,
                "fallback_count": 0,
                "latency_ms": 123.0,
                "input_tokens": 100,
                "output_tokens": 50,
                "reasoning_tokens": 10,
                "estimated_cost_usd": 0.001,
            },
            "execution_records": [],
            "error": None,
        },
    )

    result = run_benchmarks(
        agent_keys=["journal_assist"],
        output_root=tmp_path,
        max_cases=1,
    )

    latest_dir = tmp_path / "latest"
    assert (latest_dir / "raw.json").exists()
    assert (latest_dir / "scored.json").exists()
    assert (latest_dir / "summary.md").exists()
    scored = json.loads((latest_dir / "scored.json").read_text(encoding="utf-8"))
    assert scored["summary"]["total_estimated_cost_usd"] == 0.001
    assert "journal_assist" in result.agents
    assert "| Agent | Cases | Pass Rate | Avg Quality | Fallback Rate | Structured Adherence |" in (
        latest_dir / "summary.md"
    ).read_text(encoding="utf-8")
