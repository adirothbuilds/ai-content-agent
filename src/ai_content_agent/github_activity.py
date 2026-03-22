from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from ai_content_agent.settings import get_settings


GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"


@dataclass
class GitHubCommitActivity:
    sha: str
    repo_full_name: str
    message: str
    url: str
    author_login: str
    committed_at: str | None


@dataclass
class GitHubPullRequestActivity:
    number: int
    title: str
    repo_full_name: str
    state: str
    merged_at: str | None
    url: str
    author_login: str
    updated_at: str


@dataclass
class GitHubIssueActivity:
    number: int
    title: str
    repo_full_name: str
    state: str
    url: str
    author_login: str
    updated_at: str


class GitHubActivityClient:
    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        settings = get_settings()
        self._username = settings.github_username
        self._client = httpx.Client(
            base_url=GITHUB_API_BASE_URL,
            timeout=timeout,
            transport=transport,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {settings.github_token}",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
                "User-Agent": "ai-content-agent",
            },
        )

    def close(self) -> None:
        self._client.close()

    def list_commits(self, since: datetime | None = None) -> list[GitHubCommitActivity]:
        params = {
            "q": self._build_search_query("author", since=since),
            "sort": "author-date",
            "order": "desc",
            "per_page": 100,
        }
        payload = self._get_json("/search/commits", params=params)
        return [self._parse_commit(item) for item in payload.get("items", [])]

    def list_pull_requests(
        self,
        since: datetime | None = None,
    ) -> list[GitHubPullRequestActivity]:
        params = {
            "q": self._build_search_query("author", item_type="pr", since=since),
            "sort": "updated",
            "order": "desc",
            "per_page": 100,
        }
        payload = self._get_json("/search/issues", params=params)
        return [self._parse_pull_request(item) for item in payload.get("items", [])]

    def list_merged_pull_requests(
        self,
        since: datetime | None = None,
    ) -> list[GitHubPullRequestActivity]:
        params = {
            "q": self._build_search_query(
                "author",
                item_type="pr",
                merged=True,
                since=since,
            ),
            "sort": "updated",
            "order": "desc",
            "per_page": 100,
        }
        payload = self._get_json("/search/issues", params=params)
        return [self._parse_pull_request(item) for item in payload.get("items", [])]

    def list_issues(self, since: datetime | None = None) -> list[GitHubIssueActivity]:
        params = {
            "q": self._build_search_query("author", item_type="issue", since=since),
            "sort": "updated",
            "order": "desc",
            "per_page": 100,
        }
        payload = self._get_json("/search/issues", params=params)
        return [self._parse_issue(item) for item in payload.get("items", [])]

    def fetch_activity(
        self,
        since: datetime | None = None,
    ) -> dict[str, list[object]]:
        return {
            "commits": self.list_commits(since=since),
            "pull_requests": self.list_pull_requests(since=since),
            "merged_pull_requests": self.list_merged_pull_requests(since=since),
            "issues": self.list_issues(since=since),
        }

    def _build_search_query(
        self,
        actor_field: str,
        *,
        item_type: str | None = None,
        merged: bool = False,
        since: datetime | None = None,
    ) -> str:
        terms = [f"{actor_field}:{self._username}"]
        if item_type == "pr":
            terms.append("type:pr")
        elif item_type == "issue":
            terms.append("type:issue")

        if merged:
            terms.append("is:merged")
        if since is not None:
            terms.append(f"updated:>={since.date().isoformat()}")

        return " ".join(terms)

    def _get_json(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        response = self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def _parse_commit(self, payload: dict[str, Any]) -> GitHubCommitActivity:
        repository = payload.get("repository", {})
        commit = payload.get("commit", {})
        author = payload.get("author") or {}
        commit_author = commit.get("author") or {}
        return GitHubCommitActivity(
            sha=payload["sha"],
            repo_full_name=repository.get("full_name", ""),
            message=commit.get("message", ""),
            url=payload.get("html_url", ""),
            author_login=author.get("login", self._username),
            committed_at=commit_author.get("date"),
        )

    def _parse_pull_request(
        self,
        payload: dict[str, Any],
    ) -> GitHubPullRequestActivity:
        repository = _parse_repo_full_name(payload)
        user = payload.get("user") or {}
        return GitHubPullRequestActivity(
            number=payload["number"],
            title=payload.get("title", ""),
            repo_full_name=repository,
            state=payload.get("state", ""),
            merged_at=payload.get("pull_request", {}).get("merged_at"),
            url=payload.get("html_url", ""),
            author_login=user.get("login", self._username),
            updated_at=payload.get("updated_at", ""),
        )

    def _parse_issue(self, payload: dict[str, Any]) -> GitHubIssueActivity:
        repository = _parse_repo_full_name(payload)
        user = payload.get("user") or {}
        return GitHubIssueActivity(
            number=payload["number"],
            title=payload.get("title", ""),
            repo_full_name=repository,
            state=payload.get("state", ""),
            url=payload.get("html_url", ""),
            author_login=user.get("login", self._username),
            updated_at=payload.get("updated_at", ""),
        )


def _parse_repo_full_name(payload: dict[str, Any]) -> str:
    repository_url = payload.get("repository_url", "")
    if "/repos/" not in repository_url:
        return ""
    return repository_url.split("/repos/", maxsplit=1)[1]


def with_github_activity_client(
    func: Callable[[GitHubActivityClient], Any],
    *,
    transport: httpx.BaseTransport | None = None,
) -> Any:
    client = GitHubActivityClient(transport=transport)
    try:
        return func(client)
    finally:
        client.close()
