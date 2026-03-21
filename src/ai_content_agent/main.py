import os

import uvicorn


def run() -> None:
    uvicorn.run(
        "ai_content_agent.app:app",
        host=os.getenv("APP_HOST", "127.0.0.1"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    run()
