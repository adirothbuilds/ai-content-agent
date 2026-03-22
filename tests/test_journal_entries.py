from pathlib import Path

from ai_content_agent.journal_sessions import JournalSession
from ai_content_agent.services.journal_entries import build_journal_entry_document
from ai_content_agent.settings import reset_settings_cache


def test_build_journal_entry_document_contains_metadata_and_embedding(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "8000")
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGODB_DATABASE", "ai_content_agent")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-token")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.com")
    monkeypatch.setenv("CLOUDFLARED_TUNNEL_TOKEN", "cloudflare-token")
    monkeypatch.setenv("GITHUB_TOKEN", "github-token")
    monkeypatch.setenv("GITHUB_USERNAME", "adiroth")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("IDEA_PROVIDER", "openai")
    monkeypatch.setenv("IDEA_MODEL", "gpt-5")
    monkeypatch.setenv("JOURNAL_ASSIST_PROVIDER", "openai")
    monkeypatch.setenv("JOURNAL_ASSIST_MODEL", "gpt-5-mini")
    monkeypatch.setenv("SEO_PROVIDER", "gemini")
    monkeypatch.setenv("SEO_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("WRITER_PROVIDER", "anthropic")
    monkeypatch.setenv("WRITER_MODEL", "claude-sonnet-4")
    monkeypatch.setenv("REMIX_PROVIDER", "anthropic")
    monkeypatch.setenv("REMIX_MODEL", "claude-sonnet-4")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-large")
    reset_settings_cache()

    session = JournalSession(
        chat_id=456,
        user_id=100,
        current_step_index=6,
        entries={
            "work_summary": "Worked on Telegram flows.",
            "problem_solved": "Users needed guided capture.",
        },
        ai_assisted=True,
        status="confirmed",
    )

    document = build_journal_entry_document(session)

    assert document["document_type"] == "journal_entry"
    assert document["metadata"]["ai_assisted"] is True
    assert document["metadata"]["embedding_provider"] == "openai"
    assert document["metadata"]["embedding_model"] == "text-embedding-3-large"
    assert document["provenance"]["source"] == "telegram"
    assert document["entry"]["work_summary"] == "Worked on Telegram flows."
    assert len(document["embedding"]["vector"]) == 12
