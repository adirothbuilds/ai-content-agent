from ai_content_agent.journal_sessions import JournalSessionStore
from ai_content_agent.services.journal_entries import persist_confirmed_journal_entry
from ai_content_agent.telegram import TelegramAction


journal_session_store = JournalSessionStore()


def dispatch_telegram_action(action: TelegramAction) -> dict[str, object]:
    if action.chat_id is None:
        return {
            "action": "unsupported",
            "message": "Unsupported Telegram update.",
        }

    if action.type == "command":
        return _handle_command(action)

    if action.type == "message":
        result = journal_session_store.handle_message(
            chat_id=action.chat_id,
            user_id=action.user_id,
            text=action.text,
        )
        return {
            "action": result.action,
            "message": result.message,
            "session": _serialize_session(result.session),
        }

    return {
        "action": "unsupported",
        "message": "Unsupported Telegram update.",
    }


def _handle_command(action: TelegramAction) -> dict[str, object]:
    assert action.chat_id is not None

    if action.command == "journal":
        result = journal_session_store.start_session(
            chat_id=action.chat_id,
            user_id=action.user_id,
        )
    elif action.command == "assist":
        result = journal_session_store.assist_session(chat_id=action.chat_id)
    elif action.command == "accept_ai":
        result = journal_session_store.accept_ai_suggestion(chat_id=action.chat_id)
    elif action.command == "reject_ai":
        result = journal_session_store.reject_ai_suggestion(chat_id=action.chat_id)
    elif action.command == "review":
        result = journal_session_store.review_session(chat_id=action.chat_id)
    elif action.command == "save":
        result = journal_session_store.save_session(chat_id=action.chat_id)
    elif action.command == "cancel":
        result = journal_session_store.cancel_session(chat_id=action.chat_id)
    else:
        return {
            "action": "unsupported_command",
            "message": (
                "Unsupported command. Use /journal, /assist, /accept_ai, /reject_ai, /review, /save, or /cancel."
            ),
        }

    return {
        "action": result.action,
        "message": result.message,
        "session": _serialize_session(result.session),
        **_build_persistence_payload(action, result),
    }


def _serialize_session(session) -> dict[str, object] | None:
    if session is None:
        return None

    return {
        "chat_id": session.chat_id,
        "user_id": session.user_id,
        "current_step_index": session.current_step_index,
        "entries": dict(session.entries),
        "pending_ai_entries": (
            dict(session.pending_ai_entries)
            if session.pending_ai_entries is not None
            else None
        ),
        "status": session.status,
    }


def _build_persistence_payload(
    action: TelegramAction,
    result,
) -> dict[str, object]:
    if result.action != "saved" or result.session is None or action.chat_id is None:
        return {}

    journal_entry = persist_confirmed_journal_entry(result.session)
    journal_session_store.clear_session(action.chat_id)
    return {"journal_entry": journal_entry}
