from pathlib import Path
from types import SimpleNamespace

from ai_content_agent.agents.journal_assist import JournalAssistDraft, generate_journal_assist_draft
from ai_content_agent.agents.remix_agent import generate_remix_draft
from ai_content_agent.agents.seo_agent import generate_seo_revision
from ai_content_agent.agents.writer_agent import generate_writer_draft
from ai_content_agent.journal_sessions import JournalSession
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


def test_journal_assist_agent_returns_completed_draft(monkeypatch) -> None:
    _set_environment(monkeypatch)
    monkeypatch.setattr(
        "ai_content_agent.agents.journal_assist.build_agno_agent",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        "ai_content_agent.agents.journal_assist.run_agent",
        lambda *_: SimpleNamespace(
            content=JournalAssistDraft(
                work_summary="Built webhook parsing.",
                problem_solved="Webhook payloads were inconsistent.",
                tools_used="FastAPI and Pydantic.",
                lesson_learned="Keep parsing separate from routing.",
                outcome="A stable webhook contract.",
                why_it_matters="It keeps the Telegram UX grounded in real work.",
                gaps=["What problem did you solve?"],
            )
        ),
    )

    draft = generate_journal_assist_draft(
        JournalSession(chat_id=1, user_id=2, entries={"work_summary": "built webhook parsing"})
    )

    assert draft.problem_solved == "Webhook payloads were inconsistent."
    assert "What problem did you solve?" in draft.gaps


def test_writer_agent_returns_grounded_draft(monkeypatch) -> None:
    _set_environment(monkeypatch)
    monkeypatch.setattr(
        "ai_content_agent.agents.writer_agent.build_agno_agent",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        "ai_content_agent.agents.writer_agent.run_agent",
        lambda *_: SimpleNamespace(
            content=type(
                "WriterDraft",
                (),
                {
                    "model_dump": lambda self: {
                        "title": "Grounded LinkedIn Draft",
                        "draft": "Here is a grounded post draft.",
                        "source_document_ids": ["journal-1", "github-1"],
                        "provenance_summary": "Grounded in journal capture and GitHub sync work.",
                    }
                },
            )()
        ),
    )

    result = generate_writer_draft(
        idea={
            "title": "Ship with better context",
            "angle": "Combining journal and repo signals",
            "summary": "Use both sources together",
            "source_document_ids": ["journal-1", "github-1"],
        },
        context_documents=[
            {"document_id": "journal-1", "document_type": "journal_entry", "content": "Worked on capture flow."},
            {"document_id": "github-1", "document_type": "github_activity", "content": "Commit: Add sync flow."},
        ],
    )

    assert result["source_document_ids"] == ["journal-1", "github-1"]
    assert "grounded" in result["provenance_summary"].lower()


def test_seo_agent_returns_enriched_draft(monkeypatch) -> None:
    _set_environment(monkeypatch)
    monkeypatch.setattr(
        "ai_content_agent.agents.seo_agent.build_agno_agent",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        "ai_content_agent.agents.seo_agent.run_agent",
        lambda *_: SimpleNamespace(
            content=type(
                "SeoRevision",
                (),
                {
                    "model_dump": lambda self: {
                        "draft": "Polished draft with cleaner formatting.",
                        "hashtags": ["#python", "#fastapi"],
                        "rationale": "Improved readability and discoverability without changing meaning.",
                    }
                },
            )()
        ),
    )

    result = generate_seo_revision("Original draft")

    assert result["hashtags"] == ["#python", "#fastapi"]
    assert "meaning" in result["rationale"].lower()


def test_remix_agent_returns_revised_draft(monkeypatch) -> None:
    _set_environment(monkeypatch)
    monkeypatch.setattr(
        "ai_content_agent.agents.remix_agent.build_agno_agent",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        "ai_content_agent.agents.remix_agent.run_agent",
        lambda *_: SimpleNamespace(
            content=type(
                "RemixDraft",
                (),
                {
                    "model_dump": lambda self: {
                        "draft": "Revised draft with a more practical tone.",
                        "change_summary": "Tightened the opening and made the conclusion more direct.",
                    }
                },
            )()
        ),
    )

    result = generate_remix_draft(
        draft="Original draft",
        feedback="Make it more practical and less reflective.",
    )

    assert "practical tone" in result["draft"].lower()
    assert "tightened" in result["change_summary"].lower()
