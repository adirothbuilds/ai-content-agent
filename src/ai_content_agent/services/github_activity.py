from datetime import UTC, datetime
from uuid import uuid4

from ai_content_agent.embeddings import build_embedding_vector
from ai_content_agent.github_activity import (
    GitHubCommitActivity,
    GitHubIssueActivity,
    GitHubPullRequestActivity,
)
from ai_content_agent.repositories.github_activity import (
    MongoGitHubActivityRepository,
)
from ai_content_agent.settings import get_settings


_github_activity_repository = None


def persist_github_activity_documents(
    activity: dict[str, list[object]],
) -> list[dict[str, object]]:
    documents = build_github_activity_documents(activity)
    get_github_activity_repository().save_many(documents)
    return documents


def build_github_activity_documents(
    activity: dict[str, list[object]],
) -> list[dict[str, object]]:
    documents: list[dict[str, object]] = []

    for commit in activity.get("commits", []):
        documents.append(build_commit_document(commit))
    for pull_request in activity.get("pull_requests", []):
        documents.append(build_pull_request_document(pull_request, merged=False))
    for merged_pull_request in activity.get("merged_pull_requests", []):
        documents.append(build_pull_request_document(merged_pull_request, merged=True))
    for issue in activity.get("issues", []):
        documents.append(build_issue_document(issue))

    return documents


def get_github_activity_repository():
    global _github_activity_repository
    if _github_activity_repository is None:
        _github_activity_repository = MongoGitHubActivityRepository(get_settings())
    return _github_activity_repository


def set_github_activity_repository(repository) -> None:
    global _github_activity_repository
    _github_activity_repository = repository


def build_commit_document(commit: GitHubCommitActivity) -> dict[str, object]:
    content = "\n".join(
        [
            f"Commit in {commit.repo_full_name}",
            f"Message: {commit.message}",
            f"Author: {commit.author_login}",
        ]
    )
    return _build_document(
        activity_type="github_commit",
        content=content,
        source_id=commit.sha,
        repo_full_name=commit.repo_full_name,
        actor_login=commit.author_login,
        activity_timestamp=commit.committed_at,
        payload={
            "sha": commit.sha,
            "message": commit.message,
            "url": commit.url,
        },
    )


def build_pull_request_document(
    pull_request: GitHubPullRequestActivity,
    *,
    merged: bool,
) -> dict[str, object]:
    content = "\n".join(
        [
            f"{'Merged pull request' if merged else 'Pull request'} in {pull_request.repo_full_name}",
            f"Title: {pull_request.title}",
            f"Author: {pull_request.author_login}",
            f"State: {pull_request.state}",
        ]
    )
    return _build_document(
        activity_type="github_merged_pull_request" if merged else "github_pull_request",
        content=content,
        source_id=f"{pull_request.repo_full_name}#{pull_request.number}",
        repo_full_name=pull_request.repo_full_name,
        actor_login=pull_request.author_login,
        activity_timestamp=pull_request.merged_at if merged else pull_request.updated_at,
        payload={
            "number": pull_request.number,
            "title": pull_request.title,
            "state": pull_request.state,
            "merged_at": pull_request.merged_at,
            "url": pull_request.url,
        },
    )


def build_issue_document(issue: GitHubIssueActivity) -> dict[str, object]:
    content = "\n".join(
        [
            f"Issue in {issue.repo_full_name}",
            f"Title: {issue.title}",
            f"Author: {issue.author_login}",
            f"State: {issue.state}",
        ]
    )
    return _build_document(
        activity_type="github_issue",
        content=content,
        source_id=f"{issue.repo_full_name}#{issue.number}",
        repo_full_name=issue.repo_full_name,
        actor_login=issue.author_login,
        activity_timestamp=issue.updated_at,
        payload={
            "number": issue.number,
            "title": issue.title,
            "state": issue.state,
            "url": issue.url,
        },
    )


def _build_document(
    *,
    activity_type: str,
    content: str,
    source_id: str,
    repo_full_name: str,
    actor_login: str,
    activity_timestamp: str | None,
    payload: dict[str, object],
) -> dict[str, object]:
    settings = get_settings()
    created_at = datetime.now(UTC).isoformat()

    return {
        "id": str(uuid4()),
        "document_type": "github_activity",
        "content": content,
        "metadata": {
            "activity_type": activity_type,
            "repo_full_name": repo_full_name,
            "actor_login": actor_login,
            "source_id": source_id,
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
        },
        "provenance": {
            "source": "github",
            "repo_full_name": repo_full_name,
            "actor_login": actor_login,
            "source_id": source_id,
        },
        "payload": payload,
        "embedding": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "vector": build_embedding_vector(content),
        },
        "activity_timestamp": activity_timestamp,
        "created_at": created_at,
        "updated_at": created_at,
    }
