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
