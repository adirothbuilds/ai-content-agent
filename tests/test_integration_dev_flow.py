from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from ai_content_agent.app import create_app
from ai_content_agent.services.telegram import content_workflow_store, journal_session_store
from ai_content_agent.settings import reset_settings_cache


INTEGRATION_ENVIRONMENT = {
    "APP_ENV": "test",
    "APP_HOST": "127.0.0.1",
    "APP_PORT": "8000",
    "MONGODB_URI": "mongodb://127.0.0.1:27017",
    "MONGODB_DATABASE": "ai_content_agent_integration",
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


@pytest.fixture()
def integration_mongo(monkeypatch) -> Iterator[MongoClient]:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in INTEGRATION_ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    client = MongoClient(INTEGRATION_ENVIRONMENT["MONGODB_URI"], serverSelectionTimeoutMS=1000)
    try:
        client.admin.command("ping")
    except Exception as exc:  # pragma: no cover - skip path depends on local env
        client.close()
        pytest.skip(f"Local dev MongoDB is not available: {exc}")

    database = client[INTEGRATION_ENVIRONMENT["MONGODB_DATABASE"]]
    for name in (
        "journal_entries",
        "github_activity",
        "draft_history",
        "post_history",
        "post_checkpoints",
    ):
        database[name].delete_many({})

    journal_session_store.clear_session(456)
    content_workflow_store.clear_session(456)
    yield client
    client.close()


@pytest.mark.integration
def test_dev_integration_telegram_publish_flow(monkeypatch, integration_mongo: MongoClient) -> None:
    monkeypatch.setattr(
        "ai_content_agent.embeddings._embedder",
        type("FakeEmbedder", (), {"get_embedding": lambda self, text: [float(len(text)), 0.1, 0.2, 0.3]})(),
    )
    monkeypatch.setattr(
        "ai_content_agent.journal_sessions.generate_journal_assist_draft",
        lambda session: type(
            "Draft",
            (),
            {
                "work_summary": session.entries.get("work_summary", "Worked on publish flow."),
                "problem_solved": "The workflow ended before publish.",
                "tools_used": "FastAPI, Agno, MongoDB",
                "lesson_learned": "Workflow state should be persisted.",
                "outcome": "A full Telegram publishing loop.",
                "why_it_matters": "It turns the bot into a usable product.",
                "gaps": ["No further gaps."],
            },
        )(),
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.sync_github_activity",
        lambda **_: {
            "since": "2026-03-20T10:00:00+00:00",
            "counts": {"commits": 1, "pull_requests": 1, "merged_pull_requests": 0, "issues": 0},
            "documents_saved": 2,
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.generate_idea_candidates",
        lambda **_: {
            "ideas": [
                {
                    "title": "Ship the publish loop",
                    "angle": "Turn workflow state into product behavior",
                    "summary": "Explain how stored draft/post history completes the loop.",
                    "source_document_ids": ["journal-1", "github-1"],
                    "has_similar_history": False,
                    "duplicate_matches": [],
                },
                {
                    "title": "Use Mongo as working memory",
                    "angle": "Persist what matters",
                    "summary": "Show why journals, drafts, and posts all belong in memory.",
                    "source_document_ids": ["journal-1"],
                    "has_similar_history": False,
                    "duplicate_matches": [],
                },
                {
                    "title": "Keep Telegram human-in-the-loop",
                    "angle": "Approval before publish",
                    "summary": "Use explicit chat approvals to keep the user in control.",
                    "source_document_ids": ["github-1"],
                    "has_similar_history": False,
                    "duplicate_matches": [],
                },
            ],
            "context_documents": [
                {
                    "document_id": "journal-1",
                    "document_type": "journal_entry",
                    "content": "Worked on publish workflow integration.",
                    "score": 0.9,
                },
                {
                    "document_id": "github-1",
                    "document_type": "github_activity",
                    "content": "Commit: add publish flow and history.",
                    "score": 0.8,
                },
            ],
            "llm": {"model": "gpt-5", "metrics": {}, "prompt_version": "v1"},
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.generate_writer_draft",
        lambda **_: {
            "title": "Ship the publish loop",
            "draft": "I finally closed the loop from capture to publish.",
            "source_document_ids": ["journal-1", "github-1"],
            "provenance_summary": "Grounded in journal and GitHub context.",
            "prompt_version": "v1",
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.generate_seo_revision",
        lambda *_: {
            "draft": "I finally closed the loop from capture to publish.\n\n#python #ai",
            "hashtags": ["#python", "#ai"],
            "rationale": "Improved readability and discoverability.",
            "prompt_version": "v1",
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.generate_remix_draft",
        lambda **_: {
            "draft": "I finally closed the loop from capture to publish, with less friction.",
            "change_summary": "Made the opening tighter and more practical.",
            "prompt_version": "v1",
        },
    )

    client = TestClient(create_app())

    start = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 1,
            "message": {
                "message_id": 10,
                "text": "/journal",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert start.status_code == 200

    for update_id, text in enumerate(
        [
            "Worked on publish flow",
            "The workflow stopped before publish",
            "FastAPI, Agno, MongoDB",
            "Persist workflow state centrally",
            "A real publish flow",
            "It makes the bot actually usable",
        ],
        start=2,
    ):
        client.post(
            "/webhooks/telegram",
            json={
                "update_id": update_id,
                "message": {
                    "message_id": 10 + update_id,
                    "text": text,
                    "from": {"id": 100, "is_bot": False, "username": "adi"},
                    "chat": {"id": 456, "type": "private"},
                },
            },
        )

    save = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 8,
            "message": {
                "message_id": 18,
                "text": "/save",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert save.status_code == 200
    assert save.json()["dispatch"]["action"] == "saved"

    ideas = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 9,
            "message": {
                "message_id": 19,
                "text": "/ideas publish loop",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert ideas.status_code == 200
    assert ideas.json()["dispatch"]["action"] == "ideas_ready"

    select = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 10,
            "message": {
                "message_id": 20,
                "text": "/select 1",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert select.status_code == 200
    assert select.json()["dispatch"]["action"] == "idea_selected"

    draft = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 11,
            "message": {
                "message_id": 21,
                "text": "/draft",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert draft.status_code == 200
    assert draft.json()["dispatch"]["action"] == "draft_ready"
    draft_id = draft.json()["dispatch"]["draft"]["id"]

    remix = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 12,
            "message": {
                "message_id": 22,
                "text": "/remix make it more practical",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert remix.status_code == 200
    assert remix.json()["dispatch"]["action"] == "draft_remixed"
    assert remix.json()["dispatch"]["draft"]["metadata"]["parent_draft_id"] == draft_id

    publish = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 13,
            "message": {
                "message_id": 23,
                "text": "/publish",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert publish.status_code == 200
    assert publish.json()["dispatch"]["action"] == "published"

    history = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 14,
            "message": {
                "message_id": 24,
                "text": "/history",
                "from": {"id": 100, "is_bot": False, "username": "adi"},
                "chat": {"id": 456, "type": "private"},
            },
        },
    )
    assert history.status_code == 200
    assert history.json()["dispatch"]["action"] == "history"
    assert len(history.json()["dispatch"]["posts"]) == 1

    database = integration_mongo[INTEGRATION_ENVIRONMENT["MONGODB_DATABASE"]]
    assert database["journal_entries"].count_documents({}) == 1
    assert database["draft_history"].count_documents({}) == 3
    assert database["post_history"].count_documents({}) == 1
    assert database["post_checkpoints"].count_documents({}) == 1


@pytest.mark.integration
def test_dev_integration_manual_endpoints_persist_expected_documents(
    monkeypatch,
    integration_mongo: MongoClient,
) -> None:
    monkeypatch.setattr(
        "ai_content_agent.embeddings._embedder",
        type("FakeEmbedder", (), {"get_embedding": lambda self, text: [float(len(text)), 1.0, 2.0, 3.0]})(),
    )
    monkeypatch.setattr(
        "ai_content_agent.api.routes.github.sync_github_activity",
        lambda: {
            "since": "2026-03-20T10:00:00+00:00",
            "counts": {"commits": 2, "pull_requests": 1, "merged_pull_requests": 0, "issues": 0},
            "documents_saved": 3,
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.api.routes.ideas.generate_ideas_for_request",
        lambda **_: {
            "ideas": [
                {
                    "title": "Persist the workflow",
                    "angle": "Treat drafts as memory",
                    "summary": "Explain why draft history matters.",
                    "source_document_ids": ["journal-1"],
                },
                {
                    "title": "Use checkpoints",
                    "angle": "Scope by recent work",
                    "summary": "Only pull what changed since the last post.",
                    "source_document_ids": ["github-1"],
                },
                {
                    "title": "Keep Telegram simple",
                    "angle": "Approval over automation",
                    "summary": "Human-in-the-loop beats silent posting.",
                    "source_document_ids": ["journal-1", "github-1"],
                },
            ],
            "context_documents": [
                {
                    "document_id": "journal-1",
                    "document_type": "journal_entry",
                    "content": "Worked on workflow persistence.",
                    "score": 0.88,
                }
            ],
            "llm": {"model": "gpt-5", "metrics": {}, "prompt_version": "v1"},
            "github_sync": {"since": None, "counts": {}, "documents_saved": 0},
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.generate_writer_draft",
        lambda **_: {
            "title": "Persist the workflow",
            "draft": "Draft body",
            "source_document_ids": ["journal-1"],
            "provenance_summary": "Grounded in workflow context.",
            "prompt_version": "v1",
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.generate_seo_revision",
        lambda *_: {
            "draft": "Draft body\n\n#python",
            "hashtags": ["#python"],
            "rationale": "Improved formatting.",
            "prompt_version": "v1",
        },
    )
    monkeypatch.setattr(
        "ai_content_agent.services.content_workflow.generate_remix_draft",
        lambda **_: {
            "draft": "Remixed draft body",
            "change_summary": "Made it shorter.",
            "prompt_version": "v1",
        },
    )
    client = TestClient(create_app())

    journal = client.post(
        "/journal-entries",
        json={
            "chat_id": 456,
            "user_id": 100,
            "work_summary": "Built integration tests for the publish loop.",
            "problem_solved": "The workflow needed real persistence checks.",
            "tools_used": "FastAPI, pytest, MongoDB",
            "lesson_learned": "A dev integration suite catches persistence drift.",
            "outcome": "Real stored documents after each run.",
            "why_it_matters": "You can inspect the data immediately.",
        },
    )
    assert journal.status_code == 200

    sync = client.post("/github/sync")
    assert sync.status_code == 200
    assert sync.json()["sync"]["documents_saved"] == 3

    ideas = client.post("/ideas/generate", json={"prompt": "workflow memory"})
    assert ideas.status_code == 200
    assert len(ideas.json()["ideas"]) == 3

    drafts = client.post(
        "/drafts/generate",
        json={
            "chat_id": 456,
            "user_id": 100,
            "idea": {
                "title": "Persist the workflow",
                "angle": "Treat drafts as memory",
                "summary": "Explain why draft history matters.",
                "source_document_ids": ["journal-1"],
            },
            "context_documents": [
                {
                    "document_id": "journal-1",
                    "document_type": "journal_entry",
                    "content": "Worked on workflow persistence.",
                }
            ],
        },
    )
    assert drafts.status_code == 200
    seo_draft_id = drafts.json()["draft"]["id"]

    remix = client.post(f"/drafts/{seo_draft_id}/remix", json={"feedback": "Make it shorter."})
    assert remix.status_code == 200
    remix_draft_id = remix.json()["draft"]["id"]

    publish = client.post(f"/posts/{remix_draft_id}/publish")
    assert publish.status_code == 200

    history = client.get("/posts/history")
    assert history.status_code == 200
    assert len(history.json()["posts"]) == 1

    database = integration_mongo[INTEGRATION_ENVIRONMENT["MONGODB_DATABASE"]]
    journal_document = database["journal_entries"].find_one()
    assert journal_document is not None
    assert journal_document["metadata"]["capture_mode"] == "guided_telegram_session"
    assert database["draft_history"].count_documents({}) == 3
    assert database["post_history"].count_documents({}) == 1
    assert database["post_checkpoints"].count_documents({}) == 1
