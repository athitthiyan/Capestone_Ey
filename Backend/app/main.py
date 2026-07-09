"""
FastAPI application factory.
Wires middleware, lifespan, and routers for the GL Guardian backend.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import (
    agents,
    analytics,
    audit,
    auth,
    claims,
    employee_transactions,
    evaluation,
    health,
    intake,
    investigations,
    knowledge,
    reports,
    reviews,
    websocket,
)
from app.api.routes import (
    settings as settings_routes,
)
from app.core.config import settings
from app.core.request_logging import add_request_logging_middleware
from app.core.security import seed_default_user
from app.db.session import engine, init_db

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _configure_langsmith_tracing() -> None:
    """LangChain/LangGraph read tracing config from env vars, not from our Settings
    object, so mirror it in before any agent graph is built."""
    if not settings.LANGSMITH_TRACING:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    logger.info("LangSmith tracing enabled (project=%s)", settings.LANGSMITH_PROJECT)


_configure_langsmith_tracing()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting GL Guardian Backend (env=%s)", settings.ENV)
    if settings.ENV == "production":
        # Schema is managed exclusively by Alembic in production
        # (`alembic upgrade head` in the start command). create_all() here
        # would mask missing migrations and cause schema drift.
        logger.info("Skipping create_all in production; schema managed by Alembic")
    else:
        init_db()
        logger.info("Database initialized")
    seed_default_user()
    try:
        from app.db.session import SessionLocal
        from app.knowledge.retriever import sync_knowledge_embeddings

        db = SessionLocal()
        try:
            result = sync_knowledge_embeddings(db)
            logger.info("Knowledge base indexed (%s chunks)", result.get("synced_chunks", 0))
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Knowledge base indexing skipped: %s", exc)
    try:
        from app.audit.eventstore import get_audit_log

        await get_audit_log()
        logger.info("EventStoreDB initialized")
    except Exception as e:  # noqa: BLE001
        logger.warning("EventStoreDB unavailable, using Postgres audit fallback: %s", e)
    yield
    logger.info("Shutting down GL Guardian Backend")
    engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Real-time multi-agent AI audit investigation platform",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
    add_request_logging_middleware(app)

    if settings.METRICS_ENABLED:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    # Health at root; everything else under the API root path.
    app.include_router(health.router)
    app.include_router(auth.router, prefix=settings.API_ROOT_PATH)
    app.include_router(claims.router, prefix=settings.API_ROOT_PATH)
    app.include_router(investigations.router, prefix=settings.API_ROOT_PATH)
    app.include_router(reviews.router, prefix=settings.API_ROOT_PATH)
    app.include_router(evaluation.router, prefix=settings.API_ROOT_PATH)
    app.include_router(agents.router, prefix=settings.API_ROOT_PATH)
    app.include_router(analytics.router, prefix=settings.API_ROOT_PATH)
    app.include_router(reports.router, prefix=settings.API_ROOT_PATH)
    app.include_router(knowledge.router, prefix=settings.API_ROOT_PATH)
    app.include_router(audit.router, prefix=settings.API_ROOT_PATH)
    app.include_router(intake.router, prefix=settings.API_ROOT_PATH)
    app.include_router(employee_transactions.router, prefix=settings.API_ROOT_PATH)
    app.include_router(settings_routes.router, prefix=settings.API_ROOT_PATH)
    app.include_router(websocket.router, prefix=settings.API_ROOT_PATH)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            "Unhandled exception on %s %s: %s",
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )
        detail = str(exc) if settings.DEBUG else "Internal server error"
        return JSONResponse(
            status_code=500,
            content={"detail": detail, "request_id": request_id},
        )

    @app.get(f"{settings.API_ROOT_PATH}/")
    async def root():
        return {
            "message": "GL Guardian Backend API",
            "version": settings.APP_VERSION,
            "docs": "/docs",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=settings.DEBUG,
    )
