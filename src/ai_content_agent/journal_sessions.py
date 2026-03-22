from dataclasses import dataclass, field


JOURNAL_PROMPTS: tuple[tuple[str, str], ...] = (
    ("work_summary", "What did you work on?"),
    ("problem_solved", "What problem did you solve?"),
    ("tools_used", "What tools or tech were involved?"),
    ("lesson_learned", "What lesson did you learn?"),
    ("outcome", "What was the result or outcome?"),
    ("why_it_matters", "Why does it matter?"),
)


@dataclass
class JournalSession:
    chat_id: int
    user_id: int | None = None
    current_step_index: int = 0
    entries: dict[str, str] = field(default_factory=dict)
    pending_ai_entries: dict[str, str] | None = None
    status: str = "collecting"


@dataclass
class JournalSessionResult:
    action: str
    message: str
    session: JournalSession | None


class JournalSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[int, JournalSession] = {}

    def start_session(self, chat_id: int, user_id: int | None) -> JournalSessionResult:
        session = JournalSession(chat_id=chat_id, user_id=user_id)
        self._sessions[chat_id] = session
        return JournalSessionResult(
            action="started",
            message=JOURNAL_PROMPTS[0][1],
            session=session,
        )

    def get_session(self, chat_id: int) -> JournalSession | None:
        return self._sessions.get(chat_id)

    def cancel_session(self, chat_id: int) -> JournalSessionResult:
        session = self._sessions.pop(chat_id, None)
        if session is None:
            return JournalSessionResult(
                action="missing",
                message="No active journal session to cancel.",
                session=None,
            )

        return JournalSessionResult(
            action="cancelled",
            message="Journal session cancelled.",
            session=None,
        )

    def review_session(self, chat_id: int) -> JournalSessionResult:
        session = self._sessions.get(chat_id)
        if session is None:
            return JournalSessionResult(
                action="missing",
                message="No active journal session. Send /journal to start one.",
                session=None,
            )

        if session.pending_ai_entries is not None:
            return JournalSessionResult(
                action="ai_review",
                message=_build_ai_review_message(session),
                session=session,
            )

        return JournalSessionResult(
            action="review",
            message=_build_review_message(session),
            session=session,
        )

    def save_session(self, chat_id: int) -> JournalSessionResult:
        session = self._sessions.get(chat_id)
        if session is None:
            return JournalSessionResult(
                action="missing",
                message="No active journal session. Send /journal to start one.",
                session=None,
            )

        if session.pending_ai_entries is not None:
            return JournalSessionResult(
                action="confirmation_required",
                message=(
                    "AI-assisted draft requires explicit confirmation. "
                    "Send /accept_ai to use it or /reject_ai to discard it."
                ),
                session=session,
            )

        if session.current_step_index < len(JOURNAL_PROMPTS):
            _, prompt = JOURNAL_PROMPTS[session.current_step_index]
            return JournalSessionResult(
                action="incomplete",
                message=f"Journal entry is incomplete. {prompt}",
                session=session,
            )

        session.status = "reviewed"
        saved_session = JournalSession(
            chat_id=session.chat_id,
            user_id=session.user_id,
            current_step_index=session.current_step_index,
            entries=dict(session.entries),
            status="confirmed",
        )
        self._sessions.pop(chat_id, None)

        return JournalSessionResult(
            action="saved",
            message="Journal entry confirmed.\n\n" + _build_review_message(saved_session),
            session=saved_session,
        )

    def assist_session(self, chat_id: int) -> JournalSessionResult:
        session = self._sessions.get(chat_id)
        if session is None:
            return JournalSessionResult(
                action="missing",
                message="No active journal session. Send /journal to start one.",
                session=None,
            )

        session.pending_ai_entries = _build_ai_suggestion_entries(session)
        session.status = "awaiting_ai_confirmation"
        return JournalSessionResult(
            action="ai_draft_ready",
            message=_build_ai_review_message(session),
            session=session,
        )

    def accept_ai_suggestion(self, chat_id: int) -> JournalSessionResult:
        session = self._sessions.get(chat_id)
        if session is None:
            return JournalSessionResult(
                action="missing",
                message="No active journal session. Send /journal to start one.",
                session=None,
            )

        if session.pending_ai_entries is None:
            return JournalSessionResult(
                action="missing_ai_draft",
                message="No AI-assisted draft is waiting for confirmation.",
                session=session,
            )

        session.entries = dict(session.pending_ai_entries)
        session.pending_ai_entries = None
        session.current_step_index = len(JOURNAL_PROMPTS)
        session.status = "ready_for_review"
        return JournalSessionResult(
            action="ai_accepted",
            message=(
                "AI-assisted draft accepted.\n\n"
                f"{_build_review_message(session)}\n\n"
                "Send /save to confirm or /cancel to discard."
            ),
            session=session,
        )

    def reject_ai_suggestion(self, chat_id: int) -> JournalSessionResult:
        session = self._sessions.get(chat_id)
        if session is None:
            return JournalSessionResult(
                action="missing",
                message="No active journal session. Send /journal to start one.",
                session=None,
            )

        if session.pending_ai_entries is None:
            return JournalSessionResult(
                action="missing_ai_draft",
                message="No AI-assisted draft is waiting for confirmation.",
                session=session,
            )

        session.pending_ai_entries = None
        session.status = (
            "ready_for_review"
            if session.current_step_index >= len(JOURNAL_PROMPTS)
            else "collecting"
        )
        return JournalSessionResult(
            action="ai_rejected",
            message="AI-assisted draft discarded. Continue editing the journal entry manually.",
            session=session,
        )

    def handle_message(
        self,
        chat_id: int,
        user_id: int | None,
        text: str | None,
    ) -> JournalSessionResult:
        session = self._sessions.get(chat_id)
        if session is None:
            return JournalSessionResult(
                action="missing",
                message="No active journal session. Send /journal to start one.",
                session=None,
            )

        if not text:
            field_name, prompt = JOURNAL_PROMPTS[session.current_step_index]
            return JournalSessionResult(
                action="empty",
                message=f"Please send a response for {field_name}. {prompt}",
                session=session,
            )

        session.pending_ai_entries = None
        field_name, _ = JOURNAL_PROMPTS[session.current_step_index]
        session.entries[field_name] = text
        session.user_id = user_id if user_id is not None else session.user_id
        session.current_step_index += 1

        if session.current_step_index < len(JOURNAL_PROMPTS):
            _, next_prompt = JOURNAL_PROMPTS[session.current_step_index]
            return JournalSessionResult(
                action="advanced",
                message=next_prompt,
                session=session,
            )

        session.status = "ready_for_review"
        return JournalSessionResult(
            action="review_ready",
            message=(
                "Journal entry ready for review.\n\n"
                f"{_build_review_message(session)}\n\n"
                "Send /save to confirm or /cancel to discard."
            ),
            session=session,
        )


def _build_review_message(session: JournalSession) -> str:
    lines = ["Current journal entry review:"]
    for field_name, prompt in JOURNAL_PROMPTS:
        value = session.entries.get(field_name, "[missing]")
        lines.append(f"- {prompt} {value}")
    return "\n".join(lines)


def _build_ai_suggestion_entries(session: JournalSession) -> dict[str, str]:
    suggested_entries: dict[str, str] = {}
    work_summary = session.entries.get("work_summary", "your recent work")

    for field_name, prompt in JOURNAL_PROMPTS:
        if field_name in session.entries:
            suggested_entries[field_name] = _refine_text(session.entries[field_name])
            continue

        suggested_entries[field_name] = _build_missing_field_suggestion(
            field_name=field_name,
            prompt=prompt,
            work_summary=work_summary,
        )

    return suggested_entries


def _build_ai_review_message(session: JournalSession) -> str:
    assert session.pending_ai_entries is not None

    lines = ["AI-assisted journal draft ready for review:"]
    for field_name, prompt in JOURNAL_PROMPTS:
        value = session.pending_ai_entries.get(field_name, "[missing]")
        lines.append(f"- {prompt} {value}")

    lines.extend(
        [
            "",
            "Gaps identified:",
            *_build_gap_lines(session),
            "",
            "Send /accept_ai to use this draft or /reject_ai to discard it.",
        ]
    )
    return "\n".join(lines)


def _build_gap_lines(session: JournalSession) -> list[str]:
    missing_fields = [
        prompt
        for field_name, prompt in JOURNAL_PROMPTS
        if field_name not in session.entries
    ]
    if not missing_fields:
        return ["- No missing fields. The draft mainly refines the existing notes."]

    return [f"- {prompt}" for prompt in missing_fields]


def _refine_text(text: str) -> str:
    refined = text.strip()
    if not refined:
        return refined

    refined = refined[0].upper() + refined[1:]
    if refined[-1] not in ".!?":
        refined += "."
    return refined


def _build_missing_field_suggestion(
    field_name: str,
    prompt: str,
    work_summary: str,
) -> str:
    normalized_summary = work_summary.strip().rstrip(".") or "your recent work"
    prompt_map = {
        "work_summary": f"I worked on {normalized_summary.lower()}.",
        "problem_solved": (
            f"The main problem was making {normalized_summary} clearer, more reliable, and easier to use."
        ),
        "tools_used": (
            "I used FastAPI, Pydantic, and the existing Telegram webhook flow to move the work forward."
        ),
        "lesson_learned": (
            "A guided workflow works better when validation, session state, and user feedback stay separate."
        ),
        "outcome": f"The result was a clearer, more reviewable workflow around {normalized_summary}.",
        "why_it_matters": (
            "It makes progress easier to capture, review, and turn into grounded content later."
        ),
    }
    return prompt_map.get(
        field_name,
        f"Suggested follow-up for '{prompt}' based on {normalized_summary}.",
    )
