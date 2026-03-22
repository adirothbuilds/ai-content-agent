from fastapi import APIRouter, Header, HTTPException, status

from ai_content_agent.settings import get_settings
from ai_content_agent.telegram import (
    TELEGRAM_SECRET_HEADER,
    TelegramUpdate,
    parse_telegram_update,
)


router = APIRouter(prefix="/webhooks/telegram", tags=["telegram"])


@router.post("", summary="Telegram webhook")
async def telegram_webhook(
    update: TelegramUpdate,
    telegram_secret: str | None = Header(
        default=None,
        alias=TELEGRAM_SECRET_HEADER,
    ),
) -> dict[str, object]:
    settings = get_settings()

    if (
        settings.telegram_webhook_secret
        and telegram_secret != settings.telegram_webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret.",
        )

    action = parse_telegram_update(update)

    return {"ok": True, "action": action.model_dump()}
