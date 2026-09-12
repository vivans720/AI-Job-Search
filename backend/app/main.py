import uuid
import time
from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import configure_structlog, set_correlation_id, metrics
from app.api.health import router as health_router
from app.database import init_pgvector
from app.core.redis import init_redis_pool, close_redis_pool

# Initialize centralized logging
configure_structlog()
logger = structlog.get_logger(__name__)


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_correlation_id(req_id)
        
        t0 = time.perf_counter()
        response: Response = await call_next(request)
        duration_sec = time.perf_counter() - t0

        response.headers["X-Request-ID"] = req_id
        
        # Record HTTP metrics
        path_template = request.url.path
        metrics.inc("http_requests_total", status=str(response.status_code), method=request.method)
        metrics.observe("http_request_duration_seconds", duration_sec, method=request.method)
        
        return response


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

    app.add_middleware(RequestCorrelationMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count", "X-Page", "X-Page-Size", "X-Total-Pages", "X-Request-ID"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(health_router)

    from app.api.v1.router import api_v1_router
    app.include_router(api_v1_router, prefix="/api")

    return app


app = create_app()
