from fastapi import APIRouter

from app.api.v1.resumes import router as resumes_router
from app.api.v1.profile import router as profile_router
from app.api.v1.preferences import router as preferences_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.sources import router as sources_router
from app.api.v1.health import router as health_router
from app.api.v1.ai import router as ai_router

api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(resumes_router)
api_v1_router.include_router(profile_router)
api_v1_router.include_router(preferences_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(sources_router)
api_v1_router.include_router(health_router)
api_v1_router.include_router(ai_router)
