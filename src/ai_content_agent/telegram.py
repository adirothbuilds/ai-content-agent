from pydantic import BaseModel, ConfigDict, Field


TELEGRAM_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


class TelegramUser(BaseModel):
    id: int
    is_bot: bool | None = None
    username: str | None = None


class TelegramChat(BaseModel):
    id: int
    type: str


class TelegramMessage(BaseModel):
    message_id: int
    text: str | None = None
    from_user: TelegramUser | None = Field(default=None, alias="from")
    chat: TelegramChat

    model_config = ConfigDict(populate_by_name=True)


class TelegramUpdate(BaseModel):
    update_id: int
    message: TelegramMessage | None = None


class TelegramAction(BaseModel):
    type: str
    chat_id: int | None = None
    user_id: int | None = None
    command: str | None = None
    text: str | None = None
    update_id: int


def parse_telegram_update(update: TelegramUpdate) -> TelegramAction:
    if update.message is None:
        return TelegramAction(type="unsupported", update_id=update.update_id)

    message = update.message
    text = (message.text or "").strip()

    if text.startswith("/"):
        command = text.split()[0][1:]
        return TelegramAction(
            type="command",
            chat_id=message.chat.id,
            user_id=message.from_user.id if message.from_user else None,
            command=command,
            text=text,
            update_id=update.update_id,
        )

    return TelegramAction(
        type="message",
        chat_id=message.chat.id,
        user_id=message.from_user.id if message.from_user else None,
        text=text or None,
        update_id=update.update_id,
    )
