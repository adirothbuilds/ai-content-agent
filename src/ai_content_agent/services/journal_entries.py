from datetime import UTC, datetime
from uuid import uuid4

from ai_content_agent.embeddings import build_embedding_vector
from ai_content_agent.journal_schema import JOURNAL_PROMPTS
from ai_content_agent.journal_sessions import JournalSession
from ai_content_agent.repositories.journal_entries import MongoJournalEntryRepository
from ai_content_agent.settings import get_settings


_journal_entry_repository = None


def persist_confirmed_journal_entry(session: JournalSession) -> dict[str, object]:
    settings = get_settings()
    document = build_journal_entry_document(session)
    get_journal_entry_repository().save(document)
    return document


def get_journal_entry_repository():
    global _journal_entry_repository
    if _journal_entry_repository is None:
        _journal_entry_repository = MongoJournalEntryRepository(get_settings())
    return _journal_entry_repository


def set_journal_entry_repository(repository) -> None:
    global _journal_entry_repository
    _journal_entry_repository = repository


def build_journal_entry_document(session: JournalSession) -> dict[str, object]:
    settings = get_settings()
    canonical_content = _build_canonical_content(session)
    created_at = datetime.now(UTC).isoformat()

    return {
        "id": str(uuid4()),
        "document_type": "journal_entry",
        "content": canonical_content,
        "entry": dict(session.entries),
        "metadata": {
            "chat_id": session.chat_id,
            "user_id": session.user_id,
            "status": "confirmed",
            "capture_mode": "guided_telegram_session",
            "ai_assisted": session.ai_assisted,
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
        },
        "provenance": {
            "source": "telegram",
            "chat_id": session.chat_id,
            "user_id": session.user_id,
        },
        "embedding": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "vector": build_embedding_vector(canonical_content),
        },
        "created_at": created_at,
        "updated_at": created_at,
    }


def _build_canonical_content(session: JournalSession) -> str:
    lines = []
    for field_name, prompt in JOURNAL_PROMPTS:
        value = session.entries.get(field_name)
        if value:
            lines.append(f"{prompt} {value}")
    return "\n".join(lines)
