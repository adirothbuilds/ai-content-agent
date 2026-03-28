from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_content_agent.services.idea_agent import (
    IdeaAgentError,
    IdeaBatch,
    IdeaDraft,
    generate_idea_candidates,
)
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
    "OPENAI_API_KEY": "openai-key",
    "GEMINI_API_KEY": "gemini-key",
    "ANTHROPIC_API_KEY": "anthropic-key",
    "IDEA_PROVIDER": "openai",
    "IDEA_MODEL": "gpt-5",
    "JOURNAL_ASSIST_PROVIDER": "openai",
    "JOURNAL_ASSIST_MODEL": "gpt-5-mini",
    "SEO_PROVIDER": "gemini",
    "SEO_MODEL": "gemini-2.5-pro",
    "WRITER_PROVIDER": "anthropic",
    "WRITER_MODEL": "claude-sonnet-4",
    "REMIX_PROVIDER": "anthropic",
    "REMIX_MODEL": "claude-sonnet-4",
    "EMBEDDING_PROVIDER": "openai",
    "EMBEDDING_MODEL": "text-embedding-3-large",
}


def _set_environment(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()


def test_generate_idea_candidates_returns_three_grounded_ideas(monkeypatch) -> None:
    _set_environment(monkeypatch)
    monkeypatch.setattr(
        "ai_content_agent.services.idea_agent.retrieve_documents",
        lambda **_: [
            {
                "document_id": "journal-1",
                "document_type": "journal_entry",
                "content": "Worked on guided Telegram journal capture.",
                "score": 0.98,
                "metadata": {"status": "confirmed"},
                "provenance": {"source": "telegram"},
            },
            {
                "document_id": "github-1",
                "document_type": "github_activity",
                "content": "Commit in acme/repo\nMessage: Add GitHub activity sync",
                "score": 0.96,
                "metadata": {"activity_type": "github_commit"},
                "provenance": {"source": "github"},
            },
        ],
    )
    monkeypatch.setattr(
        "ai_content_agent.services.idea_agent.build_agno_agent",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        "ai_content_agent.services.idea_agent.run_agent",
        lambda *_, **__: SimpleNamespace(
            content=IdeaBatch(
                ideas=[
                    IdeaDraft(
                        title="Telegram Capture Lessons",
                        angle="What changed in the workflow",
                        summary="Show how guided journal capture improved consistency.",
                        source_document_ids=["journal-1"],
                    ),
                    IdeaDraft(
                        title="GitHub Sync as Writing Fuel",
                        angle="Using coding activity as content input",
                        summary="Explain how commit and PR history creates grounded post ideas.",
                        source_document_ids=["github-1"],
                    ),
                    IdeaDraft(
                        title="Shipping with Better Context",
                        angle="Combining journal and repo signals",
                        summary="Tell the story of using both human notes and activity data together.",
                        source_document_ids=["journal-1", "github-1"],
                    ),
                    IdeaDraft(
                        title="Repeatable Creator Workflow",
                        angle="Building a weekly cadence",
                        summary="Frame the system as a repeatable publishing loop.",
                        source_document_ids=["journal-1"],
                    ),
                    IdeaDraft(
                        title="Webhook Debugging Story",
                        angle="One bug, one lesson",
                        summary="Turn a webhook fix into a concise tactical story.",
                        source_document_ids=["github-1"],
                    ),
                ]
            ),
            model="gpt-5",
            metrics={},
        ),
    )
    monkeypatch.setattr(
        "ai_content_agent.services.idea_agent.evaluate_idea_candidates",
        lambda candidates: [
            {"candidate": candidate, "has_similar_history": False, "matches": []}
            for candidate in candidates
        ],
    )

    result = generate_idea_candidates(
        prompt="Give me grounded LinkedIn ideas from my recent work.",
    )

    assert len(result["ideas"]) == 3
    assert all(idea["source_document_ids"] for idea in result["ideas"])
    assert result["llm"]["model"] == "gpt-5"


def test_generate_idea_candidates_prefers_non_duplicate_history(monkeypatch) -> None:
    _set_environment(monkeypatch)
    monkeypatch.setattr(
        "ai_content_agent.services.idea_agent.retrieve_documents",
        lambda **_: [
            {
                "document_id": "journal-1",
                "document_type": "journal_entry",
                "content": "Worked on guided Telegram journal capture.",
                "score": 0.98,
                "metadata": {"status": "confirmed"},
                "provenance": {"source": "telegram"},
            },
            {
                "document_id": "github-1",
                "document_type": "github_activity",
                "content": "Commit in acme/repo\nMessage: Add GitHub activity sync",
                "score": 0.96,
                "metadata": {"activity_type": "github_commit"},
                "provenance": {"source": "github"},
            },
        ],
    )
    monkeypatch.setattr(
        "ai_content_agent.services.idea_agent.build_agno_agent",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        "ai_content_agent.services.idea_agent.run_agent",
        lambda *_, **__: SimpleNamespace(
            content=IdeaBatch(
                ideas=[
                    IdeaDraft(
                        title="Webhook Story",
                        angle="Bug fix narrative",
                        summary="Explain the webhook fix.",
                        source_document_ids=["github-1"],
                    ),
                    IdeaDraft(
                        title="Journal Flow Story",
                        angle="Guided capture UX",
                        summary="Explain why the journal flow improved input quality.",
                        source_document_ids=["journal-1"],
                    ),
                    IdeaDraft(
                        title="GitHub Context Story",
                        angle="Commits as writing prompts",
                        summary="Show how commits become content ideas.",
                        source_document_ids=["github-1"],
                    ),
                    IdeaDraft(
                        title="Combined Signals",
                        angle="Using journals plus code history",
                        summary="Show the value of combining sources.",
                        source_document_ids=["journal-1", "github-1"],
                    ),
                    IdeaDraft(
                        title="Publishing Cadence",
                        angle="Weekly creator system",
                        summary="Turn the workflow into a repeatable system.",
                        source_document_ids=["journal-1"],
                    ),
                ]
            ),
            model="gpt-5",
            metrics={},
        ),
    )
    monkeypatch.setattr(
        "ai_content_agent.services.idea_agent.evaluate_idea_candidates",
        lambda candidates: [
            {
                "candidate": candidates[0],
                "has_similar_history": True,
                "matches": [{"document_id": "post-1", "score": 0.97}],
            },
            {"candidate": candidates[1], "has_similar_history": False, "matches": []},
            {"candidate": candidates[2], "has_similar_history": False, "matches": []},
            {"candidate": candidates[3], "has_similar_history": False, "matches": []},
            {
                "candidate": candidates[4],
                "has_similar_history": True,
                "matches": [{"document_id": "post-2", "score": 0.95}],
            },
        ],
    )

    result = generate_idea_candidates(
        prompt="Generate idea candidates from recent work.",
    )

    assert len(result["ideas"]) == 3
    assert {idea["title"] for idea in result["ideas"]} == {
        "Journal Flow Story",
        "GitHub Context Story",
        "Combined Signals",
    }
    assert all(not idea["has_similar_history"] for idea in result["ideas"])


def test_generate_idea_candidates_requires_grounded_context(monkeypatch) -> None:
    _set_environment(monkeypatch)
    monkeypatch.setattr(
        "ai_content_agent.services.idea_agent.retrieve_documents",
        lambda **_: [],
    )

    with pytest.raises(IdeaAgentError, match="requires retrieved journal or GitHub context"):
        generate_idea_candidates(prompt="Generate ideas from nothing")
