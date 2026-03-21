from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai_content_agent.api.routes.health import router as health_router
from ai_content_agent.settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_settings()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="AI Content Agent", lifespan=lifespan)
    app.include_router(health_router)
    return app


app = create_app()
