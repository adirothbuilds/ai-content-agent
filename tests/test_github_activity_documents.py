from pathlib import Path

from ai_content_agent.github_activity import (
    GitHubCommitActivity,
    GitHubIssueActivity,
    GitHubPullRequestActivity,
)
from ai_content_agent.services.github_activity import (
    build_github_activity_documents,
    persist_github_activity_documents,
    set_github_activity_repository,
)
from ai_content_agent.settings import reset_settings_cache


ENVIRONMENT = {
    "APP_ENV": "test",
    "APP_HOST": "127.0.0.1",
    "APP_PORT": "8000",
    "MONGODB_URI": "mongodb://localhost:27017",
    "MONGODB_DATABASE": "ai_content_agent",
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


class FakeGitHubActivityRepository:
    def __init__(self) -> None:
        self.documents: list[dict[str, object]] = []

    def save_many(self, documents) -> None:
        self.documents.extend([dict(document) for document in documents])


def test_build_github_activity_documents_uses_shared_schema(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    activity = {
        "commits": [
            GitHubCommitActivity(
                sha="abc123",
                repo_full_name="acme/repo",
                message="Add webhook flow",
                url="https://github.com/acme/repo/commit/abc123",
                author_login="adiroth",
                committed_at="2026-03-22T12:00:00Z",
            )
        ],
        "pull_requests": [
            GitHubPullRequestActivity(
                number=42,
                title="Improve webhook parsing",
                repo_full_name="acme/repo",
                state="open",
                merged_at=None,
                url="https://github.com/acme/repo/pull/42",
                author_login="adiroth",
                updated_at="2026-03-22T12:30:00Z",
            )
        ],
        "merged_pull_requests": [],
        "issues": [
            GitHubIssueActivity(
                number=7,
                title="Support review step",
                repo_full_name="acme/repo",
                state="open",
                url="https://github.com/acme/repo/issues/7",
                author_login="adiroth",
                updated_at="2026-03-22T12:45:00Z",
            )
        ],
    }

    documents = build_github_activity_documents(activity)

    assert len(documents) == 3
    assert {document["document_type"] for document in documents} == {"github_activity"}
    assert documents[0]["metadata"]["activity_type"] == "github_commit"
    assert documents[1]["metadata"]["activity_type"] == "github_pull_request"
    assert documents[2]["metadata"]["activity_type"] == "github_issue"
    assert documents[0]["provenance"]["source"] == "github"
    assert documents[0]["metadata"]["embedding_provider"] == "openai"
    assert len(documents[0]["embedding"]["vector"]) == 12


def test_persist_github_activity_documents_saves_all_documents(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    repository = FakeGitHubActivityRepository()
    set_github_activity_repository(repository)

    activity = {
        "commits": [
            GitHubCommitActivity(
                sha="abc123",
                repo_full_name="acme/repo",
                message="Add webhook flow",
                url="https://github.com/acme/repo/commit/abc123",
                author_login="adiroth",
                committed_at="2026-03-22T12:00:00Z",
            )
        ],
        "pull_requests": [],
        "merged_pull_requests": [
            GitHubPullRequestActivity(
                number=43,
                title="Ship review step",
                repo_full_name="acme/repo",
                state="closed",
                merged_at="2026-03-22T13:00:00Z",
                url="https://github.com/acme/repo/pull/43",
                author_login="adiroth",
                updated_at="2026-03-22T13:00:00Z",
            )
        ],
        "issues": [],
    }

    documents = persist_github_activity_documents(activity)

    assert len(documents) == 2
    assert len(repository.documents) == 2
    assert repository.documents[1]["metadata"]["activity_type"] == "github_merged_pull_request"
