from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ai_content_agent.repositories.checkpoints import MongoCheckpointRepository
from ai_content_agent.settings import get_settings


_checkpoint_repository = None


def resolve_activity_since(
    *,
    explicit_topic_requested: bool = False,
    now: datetime | None = None,
) -> datetime | None:
    if explicit_topic_requested:
        return None

    settings = get_settings()
    current_time = now or datetime.now(UTC)
    checkpoint = get_checkpoint_repository().get_last_published_checkpoint()

    if checkpoint and checkpoint.get("published_at"):
        return _parse_timestamp(checkpoint["published_at"])

    return current_time - timedelta(days=settings.delta_lookback_days_fallback)


def save_last_published_checkpoint(
    *,
    published_at: datetime,
    post_id: str,
) -> dict[str, object]:
    document = {
        "id": str(uuid4()),
        "checkpoint_type": "last_published_post",
        "post_id": post_id,
        "published_at": published_at.astimezone(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    get_checkpoint_repository().save_last_published_checkpoint(document)
    return document


def get_checkpoint_repository():
    global _checkpoint_repository
    if _checkpoint_repository is None:
        _checkpoint_repository = MongoCheckpointRepository(get_settings())
    return _checkpoint_repository


def set_checkpoint_repository(repository) -> None:
    global _checkpoint_repository
    _checkpoint_repository = repository


def _parse_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(UTC)
