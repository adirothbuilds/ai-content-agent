import os

import uvicorn

from ai_content_agent.settings import get_settings


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "ai_content_agent.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
