from ai_content_agent.journal_sessions import JournalSessionStore
from ai_content_agent.services.content_workflow import ContentWorkflowStore
from ai_content_agent.services.journal_entries import persist_confirmed_journal_entry
from ai_content_agent.telegram import TelegramAction


journal_session_store = JournalSessionStore()
content_workflow_store = ContentWorkflowStore()


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
    command_argument = _extract_command_argument(action.text)

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
    elif action.command == "ideas":
        result = content_workflow_store.generate_ideas(
            chat_id=action.chat_id,
            user_id=action.user_id,
            prompt=command_argument,
        )
    elif action.command == "select":
        if not command_argument or not command_argument.isdigit():
            return {
                "action": "invalid_selection",
                "message": "Use /select <number> after generating ideas.",
            }
        result = content_workflow_store.select_idea(
            chat_id=action.chat_id,
            selection=int(command_argument),
        )
    elif action.command == "draft":
        result = content_workflow_store.generate_draft(chat_id=action.chat_id)
    elif action.command == "remix":
        if not command_argument:
            return {
                "action": "missing_feedback",
                "message": "Use /remix <feedback> to revise the current draft.",
            }
        result = content_workflow_store.remix_draft(
            chat_id=action.chat_id,
            feedback=command_argument,
        )
    elif action.command == "publish":
        result = content_workflow_store.publish(chat_id=action.chat_id)
    elif action.command == "history":
        result = content_workflow_store.history(chat_id=action.chat_id)
    else:
        return {
            "action": "unsupported_command",
            "message": (
                "Unsupported command. Use /journal, /assist, /accept_ai, /reject_ai, /review, /save, /cancel, /ideas, /select, /draft, /remix, /publish, or /history."
            ),
        }

    response = {
        "action": result.action,
        "message": result.message,
        "session": _serialize_session(result.session),
    }
    response.update(_build_persistence_payload(action, result))
    response.update(_build_content_workflow_payload(result))
    return response


def _serialize_session(session) -> dict[str, object] | None:
    if session is None or not hasattr(session, "current_step_index"):
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
        "pending_ai_gaps": (
            list(session.pending_ai_gaps)
            if session.pending_ai_gaps is not None
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


def _build_content_workflow_payload(result) -> dict[str, object]:
    if not hasattr(result, "payload"):
        return {}

    payload = dict(result.payload)
    if hasattr(result, "session"):
        payload["content_session"] = _serialize_content_session(result.session)
    return payload


def _serialize_content_session(session) -> dict[str, object] | None:
    if session is None or not hasattr(session, "idea_candidates"):
        return None

    return {
        "chat_id": session.chat_id,
        "user_id": session.user_id,
        "idea_prompt": session.idea_prompt,
        "idea_candidates": list(session.idea_candidates),
        "context_documents": list(session.context_documents),
        "selected_idea_index": session.selected_idea_index,
        "current_draft_id": session.current_draft_id,
        "status": session.status,
    }


def _extract_command_argument(text: str | None) -> str | None:
    if not text:
        return None
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    value = parts[1].strip()
    return value or None
