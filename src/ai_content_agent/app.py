from fastapi import FastAPI

from ai_content_agent.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Content Agent")
    app.include_router(health_router)
    return app


app = create_app()
