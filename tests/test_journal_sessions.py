from ai_content_agent.journal_sessions import JournalSessionStore


def test_journal_session_advances_through_all_prompts() -> None:
    store = JournalSessionStore()
    start = store.start_session(chat_id=1, user_id=2)

    assert start.action == "started"
    assert start.message == "What did you work on?"

    prompts = [
        "Built webhook parsing",
        "Webhook payloads were inconsistent",
        "FastAPI and Pydantic",
        "Keep parsing separate from routing",
        "A stable webhook contract",
        "It keeps the Telegram UX grounded in real work",
    ]

    last_result = None
    for prompt in prompts:
        last_result = store.handle_message(chat_id=1, user_id=2, text=prompt)

    assert last_result is not None
    assert last_result.action == "review_ready"
    assert "Send /save to confirm or /cancel to discard." in last_result.message
    assert last_result.session is not None
    assert last_result.session.entries["work_summary"] == "Built webhook parsing"
    assert last_result.session.status == "ready_for_review"


def test_journal_session_review_and_save_require_completed_flow() -> None:
    store = JournalSessionStore()
    store.start_session(chat_id=1, user_id=2)

    incomplete_save = store.save_session(chat_id=1)
    assert incomplete_save.action == "incomplete"

    store.handle_message(chat_id=1, user_id=2, text="Worked on the bot")
    review = store.review_session(chat_id=1)

    assert review.action == "review"
    assert "- What did you work on? Worked on the bot" in review.message
    assert "[missing]" in review.message


def test_journal_session_cancel_clears_state() -> None:
    store = JournalSessionStore()
    store.start_session(chat_id=1, user_id=2)

    cancelled = store.cancel_session(chat_id=1)
    after_cancel = store.review_session(chat_id=1)

    assert cancelled.action == "cancelled"
    assert after_cancel.action == "missing"


def test_journal_session_ai_assist_requires_explicit_confirmation_before_save() -> None:
    store = JournalSessionStore()
    store.start_session(chat_id=1, user_id=2)
    store.handle_message(chat_id=1, user_id=2, text="built webhook parsing")

    ai_draft = store.assist_session(chat_id=1)
    blocked_save = store.save_session(chat_id=1)
    accepted = store.accept_ai_suggestion(chat_id=1)

    assert ai_draft.action == "ai_draft_ready"
    assert "Gaps identified:" in ai_draft.message
    assert blocked_save.action == "confirmation_required"
    assert accepted.action == "ai_accepted"
    assert accepted.session is not None
    assert accepted.session.status == "ready_for_review"

    saved = store.save_session(chat_id=1)
    assert saved.action == "saved"
    assert saved.session is not None
    assert saved.session.status == "confirmed"
    assert saved.session.ai_assisted is True
