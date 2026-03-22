from __future__ import annotations

from ai_content_agent.github_activity import with_github_activity_client
from ai_content_agent.services.checkpoints import resolve_activity_since
from ai_content_agent.services.github_activity import persist_github_activity_documents


def sync_github_activity(
    *,
    explicit_topic_requested: bool = False,
) -> dict[str, object]:
    since = resolve_activity_since(explicit_topic_requested=explicit_topic_requested)
    activity = with_github_activity_client(lambda client: client.fetch_activity(since=since))
    documents = persist_github_activity_documents(activity)
    return {
        "since": since.isoformat() if since is not None else None,
        "counts": {
            key: len(value)
            for key, value in activity.items()
        },
        "documents_saved": len(documents),
    }
