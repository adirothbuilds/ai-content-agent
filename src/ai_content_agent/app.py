from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai_content_agent.api.routes.drafts import router as drafts_router
from ai_content_agent.api.routes.github import router as github_router
from ai_content_agent.api.routes.health import router as health_router
from ai_content_agent.api.routes.ideas import router as ideas_router
from ai_content_agent.api.routes.journal_entries import router as journal_entries_router
from ai_content_agent.api.routes.posts import router as posts_router
from ai_content_agent.api.routes.telegram import router as telegram_router
from ai_content_agent.observability import configure_logging, observability_middleware
from ai_content_agent.settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="AI Content Agent", lifespan=lifespan)
    app.middleware("http")(observability_middleware)
    app.include_router(health_router)
    app.include_router(telegram_router)
    app.include_router(journal_entries_router)
    app.include_router(github_router)
    app.include_router(ideas_router)
    app.include_router(drafts_router)
    app.include_router(posts_router)
    return app


app = create_app()
