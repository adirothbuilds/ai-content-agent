from datetime import datetime
from pathlib import Path

import httpx

from ai_content_agent.github_activity import GitHubActivityClient
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


def test_github_activity_client_uses_authenticated_user_scoped_queries(monkeypatch) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/search/commits":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "sha": "abc123",
                            "html_url": "https://github.com/acme/repo/commit/abc123",
                            "repository": {"full_name": "acme/repo"},
                            "author": {"login": "adiroth"},
                            "commit": {
                                "message": "Add webhook flow",
                                "author": {"date": "2026-03-22T12:00:00Z"},
                            },
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "number": 42,
                        "title": "Improve webhook parsing",
                        "state": "open",
                        "html_url": "https://github.com/acme/repo/pull/42",
                        "repository_url": "https://api.github.com/repos/acme/repo",
                        "user": {"login": "adiroth"},
                        "updated_at": "2026-03-22T12:30:00Z",
                        "pull_request": {"merged_at": "2026-03-22T13:00:00Z"},
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = GitHubActivityClient(transport=transport)

    try:
        commits = client.list_commits()
        pull_requests = client.list_pull_requests()
        merged_pull_requests = client.list_merged_pull_requests()
        issues = client.list_issues(since=datetime(2026, 3, 20))
    finally:
        client.close()

    assert commits[0].repo_full_name == "acme/repo"
    assert commits[0].author_login == "adiroth"
    assert pull_requests[0].repo_full_name == "acme/repo"
    assert merged_pull_requests[0].merged_at == "2026-03-22T13:00:00Z"
    assert issues[0].title == "Improve webhook parsing"

    assert requests[0].headers["Authorization"] == "Bearer github-token"
    assert requests[0].headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert requests[0].url.params["q"] == "author:adiroth"
    assert requests[1].url.params["q"] == "author:adiroth type:pr"
    assert requests[2].url.params["q"] == "author:adiroth type:pr is:merged"
    assert requests[3].url.params["q"] == "author:adiroth type:issue updated:>=2026-03-20"


def test_github_activity_client_fetch_activity_returns_all_supported_groups(
    monkeypatch,
) -> None:
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    for key, value in ENVIRONMENT.items():
        monkeypatch.setenv(key, value)
    reset_settings_cache()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search/commits":
            return httpx.Response(200, json={"items": []})
        return httpx.Response(200, json={"items": []})

    client = GitHubActivityClient(transport=httpx.MockTransport(handler))
    try:
        activity = client.fetch_activity()
    finally:
        client.close()

    assert set(activity) == {
        "commits",
        "pull_requests",
        "merged_pull_requests",
        "issues",
    }
