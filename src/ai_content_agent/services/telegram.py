from ai_content_agent.journal_sessions import JournalSessionStore
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
                "Unsupported command. Use /journal, /review, /save, or /cancel."
            ),
        }

    return {
        "action": result.action,
        "message": result.message,
        "session": _serialize_session(result.session),
    }


def _serialize_session(session) -> dict[str, object] | None:
    if session is None:
        return None

    return {
        "chat_id": session.chat_id,
        "user_id": session.user_id,
        "current_step_index": session.current_step_index,
        "entries": dict(session.entries),
        "status": session.status,
    }
