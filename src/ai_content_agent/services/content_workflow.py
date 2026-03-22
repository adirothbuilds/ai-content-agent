from __future__ import annotations

from dataclasses import dataclass, field

from ai_content_agent.agents.remix_agent import generate_remix_draft
from ai_content_agent.agents.seo_agent import generate_seo_revision
from ai_content_agent.agents.writer_agent import generate_writer_draft
from ai_content_agent.services.draft_history import (
    get_draft_history_repository,
    persist_draft_history_document,
)
from ai_content_agent.services.github_sync import sync_github_activity
from ai_content_agent.services.idea_agent import IdeaAgentError, generate_idea_candidates
from ai_content_agent.services.post_history_records import list_recent_post_history, publish_draft_history_document


DEFAULT_IDEA_PROMPT = "Generate grounded LinkedIn ideas from my recent work."


@dataclass
class ContentWorkflowSession:
    chat_id: int
    user_id: int | None = None
    idea_prompt: str | None = None
    idea_candidates: list[dict[str, object]] = field(default_factory=list)
    context_documents: list[dict[str, object]] = field(default_factory=list)
    selected_idea_index: int | None = None
    current_draft_id: str | None = None
    status: str = "idle"


@dataclass
class ContentWorkflowResult:
    action: str
    message: str
    session: ContentWorkflowSession | None
    payload: dict[str, object] = field(default_factory=dict)


class ContentWorkflowStore:
    def __init__(self) -> None:
        self._sessions: dict[int, ContentWorkflowSession] = {}

    def get_session(self, chat_id: int) -> ContentWorkflowSession | None:
        return self._sessions.get(chat_id)

    def clear_session(self, chat_id: int) -> None:
        self._sessions.pop(chat_id, None)

    def generate_ideas(
        self,
        *,
        chat_id: int,
        user_id: int | None,
        prompt: str | None = None,
    ) -> ContentWorkflowResult:
        session = self._sessions.get(chat_id) or ContentWorkflowSession(
            chat_id=chat_id,
            user_id=user_id,
        )
        session.user_id = user_id if user_id is not None else session.user_id
        explicit_prompt = bool(prompt)
        idea_prompt = (prompt or DEFAULT_IDEA_PROMPT).strip()

        try:
            sync_summary = sync_github_activity(explicit_topic_requested=explicit_prompt)
            result = generate_idea_candidates(prompt=idea_prompt)
        except IdeaAgentError as exc:
            return ContentWorkflowResult(
                action="error",
                message=str(exc),
                session=session,
            )

        session.idea_prompt = idea_prompt
        session.idea_candidates = list(result["ideas"])
        session.context_documents = list(result["context_documents"])
        session.selected_idea_index = None
        session.current_draft_id = None
        session.status = "ideas_ready"
        self._sessions[chat_id] = session
        return ContentWorkflowResult(
            action="ideas_ready",
            message=_build_idea_selection_message(session),
            session=session,
            payload={
                "ideas": list(session.idea_candidates),
                "context_documents": list(session.context_documents),
                "github_sync": sync_summary,
                "llm": dict(result["llm"]),
            },
        )

    def select_idea(
        self,
        *,
        chat_id: int,
        selection: int,
    ) -> ContentWorkflowResult:
        session = self._sessions.get(chat_id)
        if session is None or not session.idea_candidates:
            return ContentWorkflowResult(
                action="missing",
                message="No idea candidates are ready. Send /ideas first.",
                session=session,
            )

        if selection < 1 or selection > len(session.idea_candidates):
            return ContentWorkflowResult(
                action="invalid_selection",
                message=f"Choose an idea number between 1 and {len(session.idea_candidates)}.",
                session=session,
            )

        session.selected_idea_index = selection - 1
        session.status = "idea_selected"
        idea = session.idea_candidates[session.selected_idea_index]
        return ContentWorkflowResult(
            action="idea_selected",
            message=(
                f"Selected idea {selection}: {idea['title']}\n\n"
                "Send /draft to approve draft generation."
            ),
            session=session,
            payload={"selected_idea": dict(idea)},
        )

    def generate_draft(self, *, chat_id: int) -> ContentWorkflowResult:
        session = self._sessions.get(chat_id)
        if session is None or session.selected_idea_index is None:
            return ContentWorkflowResult(
                action="missing",
                message="No idea is selected. Send /ideas and then /select <number>.",
                session=session,
            )

        idea = session.idea_candidates[session.selected_idea_index]
        context_documents = _select_context_documents(
            session.context_documents,
            idea["source_document_ids"],
        )
        writer_output = generate_writer_draft(
            idea=idea,
            context_documents=context_documents,
        )
        writer_document = persist_draft_history_document(
            chat_id=session.chat_id,
            user_id=session.user_id,
            idea=idea,
            draft_payload=writer_output,
            workflow_stage="writer",
        )

        seo_output = generate_seo_revision(writer_output["draft"])
        seo_payload = {
            "title": writer_output["title"],
            "draft": seo_output["draft"],
            "hashtags": seo_output["hashtags"],
            "rationale": seo_output["rationale"],
            "source_document_ids": writer_output["source_document_ids"],
            "provenance_summary": writer_output["provenance_summary"],
        }
        seo_document = persist_draft_history_document(
            chat_id=session.chat_id,
            user_id=session.user_id,
            idea=idea,
            draft_payload=seo_payload,
            workflow_stage="seo",
            parent_draft_id=str(writer_document["id"]),
        )

        session.current_draft_id = str(seo_document["id"])
        session.status = "draft_ready"
        return ContentWorkflowResult(
            action="draft_ready",
            message=_build_draft_message(seo_document),
            session=session,
            payload={
                "writer_draft": writer_document,
                "draft": seo_document,
            },
        )

    def remix_draft(
        self,
        *,
        chat_id: int,
        feedback: str,
    ) -> ContentWorkflowResult:
        session = self._sessions.get(chat_id)
        if session is None or not session.current_draft_id:
            return ContentWorkflowResult(
                action="missing",
                message="No current draft is ready. Send /draft after selecting an idea.",
                session=session,
            )

        current_draft = get_draft_history_repository().get_by_id(session.current_draft_id)
        if current_draft is None:
            return ContentWorkflowResult(
                action="missing",
                message="Current draft could not be loaded.",
                session=session,
            )

        remixed = generate_remix_draft(
            draft=str(current_draft["payload"]["draft"]),
            feedback=feedback,
        )
        remixed_payload = {
            "title": current_draft["payload"].get("title"),
            "draft": remixed["draft"],
            "hashtags": list(current_draft["payload"].get("hashtags", [])),
            "change_summary": remixed["change_summary"],
            "source_document_ids": list(current_draft["metadata"].get("source_document_ids", [])),
            "provenance_summary": current_draft["payload"].get("provenance_summary"),
        }
        idea = {
            "title": current_draft["metadata"].get("selected_idea_title", "Selected idea"),
            "angle": current_draft["metadata"].get("selected_idea_angle", ""),
        }
        remixed_document = persist_draft_history_document(
            chat_id=session.chat_id,
            user_id=session.user_id,
            idea=idea,
            draft_payload=remixed_payload,
            workflow_stage="remix",
            parent_draft_id=str(current_draft["id"]),
        )
        session.current_draft_id = str(remixed_document["id"])
        session.status = "draft_ready"
        return ContentWorkflowResult(
            action="draft_remixed",
            message=_build_draft_message(remixed_document),
            session=session,
            payload={"draft": remixed_document},
        )

    def publish(self, *, chat_id: int) -> ContentWorkflowResult:
        session = self._sessions.get(chat_id)
        if session is None or not session.current_draft_id:
            return ContentWorkflowResult(
                action="missing",
                message="No draft is ready to publish. Generate a draft first.",
                session=session,
            )

        current_draft = get_draft_history_repository().get_by_id(session.current_draft_id)
        if current_draft is None:
            return ContentWorkflowResult(
                action="missing",
                message="Current draft could not be loaded.",
                session=session,
            )

        post = publish_draft_history_document(
            draft_document=current_draft,
            chat_id=session.chat_id,
            user_id=session.user_id,
        )
        session.status = "published"
        return ContentWorkflowResult(
            action="published",
            message=_build_publish_message(post),
            session=session,
            payload={"post": post, "checkpoint": dict(post["checkpoint"])},
        )

    def history(self, *, chat_id: int, limit: int = 5) -> ContentWorkflowResult:
        session = self._sessions.get(chat_id) or ContentWorkflowSession(chat_id=chat_id)
        posts = list_recent_post_history(limit=limit)
        return ContentWorkflowResult(
            action="history",
            message=_build_history_message(posts),
            session=session,
            payload={"posts": posts},
        )


def generate_ideas_for_request(*, prompt: str | None = None) -> dict[str, object]:
    explicit_prompt = bool(prompt)
    sync_summary = sync_github_activity(explicit_topic_requested=explicit_prompt)
    result = generate_idea_candidates(prompt=(prompt or DEFAULT_IDEA_PROMPT).strip())
    return {
        **result,
        "github_sync": sync_summary,
    }


def generate_draft_for_request(
    *,
    chat_id: int | None,
    user_id: int | None,
    idea: dict[str, object],
    context_documents: list[dict[str, object]],
) -> dict[str, object]:
    writer_output = generate_writer_draft(idea=idea, context_documents=context_documents)
    writer_document = persist_draft_history_document(
        chat_id=chat_id,
        user_id=user_id,
        idea=idea,
        draft_payload=writer_output,
        workflow_stage="writer",
    )
    seo_output = generate_seo_revision(writer_output["draft"])
    seo_payload = {
        "title": writer_output["title"],
        "draft": seo_output["draft"],
        "hashtags": seo_output["hashtags"],
        "rationale": seo_output["rationale"],
        "source_document_ids": writer_output["source_document_ids"],
        "provenance_summary": writer_output["provenance_summary"],
    }
    seo_document = persist_draft_history_document(
        chat_id=chat_id,
        user_id=user_id,
        idea=idea,
        draft_payload=seo_payload,
        workflow_stage="seo",
        parent_draft_id=str(writer_document["id"]),
    )
    return {
        "writer_draft": writer_document,
        "draft": seo_document,
    }


def remix_draft_for_request(*, draft_id: str, feedback: str) -> dict[str, object]:
    current_draft = get_draft_history_repository().get_by_id(draft_id)
    if current_draft is None:
        raise ValueError("Draft not found.")

    remixed = generate_remix_draft(
        draft=str(current_draft["payload"]["draft"]),
        feedback=feedback,
    )
    remixed_payload = {
        "title": current_draft["payload"].get("title"),
        "draft": remixed["draft"],
        "hashtags": list(current_draft["payload"].get("hashtags", [])),
        "change_summary": remixed["change_summary"],
        "source_document_ids": list(current_draft["metadata"].get("source_document_ids", [])),
        "provenance_summary": current_draft["payload"].get("provenance_summary"),
    }
    idea = {
        "title": current_draft["metadata"].get("selected_idea_title", "Selected idea"),
        "angle": current_draft["metadata"].get("selected_idea_angle", ""),
    }
    draft = persist_draft_history_document(
        chat_id=current_draft["metadata"].get("chat_id"),
        user_id=current_draft["metadata"].get("user_id"),
        idea=idea,
        draft_payload=remixed_payload,
        workflow_stage="remix",
        parent_draft_id=str(current_draft["id"]),
    )
    return {"draft": draft}


def publish_draft_for_request(*, draft_id: str) -> dict[str, object]:
    draft = get_draft_history_repository().get_by_id(draft_id)
    if draft is None:
        raise ValueError("Draft not found.")

    post = publish_draft_history_document(
        draft_document=draft,
        chat_id=draft["metadata"].get("chat_id"),
        user_id=draft["metadata"].get("user_id"),
    )
    return {"post": post, "checkpoint": dict(post["checkpoint"])}


def _select_context_documents(
    context_documents: list[dict[str, object]],
    source_document_ids: list[str],
) -> list[dict[str, object]]:
    preferred_ids = {str(value) for value in source_document_ids}
    selected = [
        document
        for document in context_documents
        if str(document.get("document_id")) in preferred_ids
    ]
    return selected or context_documents


def _build_idea_selection_message(session: ContentWorkflowSession) -> str:
    lines = ["Idea candidates:"]
    for index, idea in enumerate(session.idea_candidates, start=1):
        lines.extend(
            [
                f"{index}. {idea['title']}",
                f"   Angle: {idea['angle']}",
                f"   Summary: {idea['summary']}",
            ]
        )
    lines.append("")
    lines.append("Send /select <number> to choose one idea.")
    return "\n".join(lines)


def _build_draft_message(draft_document: dict[str, object]) -> str:
    payload = draft_document["payload"]
    hashtags = payload.get("hashtags") or []
    lines = [
        "Current draft:",
        str(payload.get("draft", "")),
    ]
    if hashtags:
        lines.append("")
        lines.append(f"Hashtags: {' '.join(hashtags)}")
    lines.append("")
    lines.append("Send /remix <feedback> to revise it or /publish to finalize it.")
    return "\n".join(lines)


def _build_publish_message(post: dict[str, object]) -> str:
    title = post.get("payload", {}).get("title") or "Published post"
    return (
        f"{title} published.\n\n"
        "The post was saved to history and the publish checkpoint was updated."
    )


def _build_history_message(posts: list[dict[str, object]]) -> str:
    if not posts:
        return "No published post history is available yet."

    lines = ["Recent published posts:"]
    for index, post in enumerate(posts, start=1):
        payload = post.get("payload", {})
        title = payload.get("title") or f"Post {index}"
        preview = str(payload.get("draft", "")).splitlines()[0][:120]
        published_at = str(post.get("published_at", ""))[:19]
        lines.append(f"{index}. {title} ({published_at})")
        if preview:
            lines.append(f"   {preview}")
    return "\n".join(lines)
