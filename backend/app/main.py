from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.database import init_pgvector

from app.core.redis import init_redis_pool, close_redis_pool

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_startup")
    try:
        await init_pgvector()
        logger.info("pgvector_extension_verified")
    except Exception as e:
        logger.error("pgvector_init_failed", error=str(e))

    try:
        await init_redis_pool()
    except Exception as e:
        logger.warning("redis_startup_warning", error=str(e))

    from app.services.scheduler_service import scheduler_service
    scheduler_service.start()

    yield

    scheduler_service.stop()
    await close_redis_pool()
    logger.info("application_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Job Agent India",
        description="Deterministic backend for job search, matching, and recommendation",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count", "X-Page", "X-Page-Size", "X-Total-Pages"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(health_router)

    from app.api.v1.router import api_v1_router
    app.include_router(api_v1_router, prefix="/api")

    return app


app = create_app()
