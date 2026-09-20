from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.services.browser_session_service import BrowserSessionService

router = APIRouter(prefix="/browser/sessions", tags=["Browser Sessions"])


class PlatformSessionResponse(BaseModel):
    platform: str
    display_name: str | None = None
    supported: bool
    enabled: bool = False
    connected: bool = False
    has_stored_session: bool = False
    profile_dir: str | None = None
    last_active_at: str | None = None
    login_url: str | None = None
    mode: str = "public_discovery_default"


class AllSessionsResponse(BaseModel):
    status: str
    default_mode: str
    sessions: dict[str, Any]
    checked_at: str


class VerifySessionResponse(BaseModel):
    status: str
    platform: str
    authenticated: bool
    current_url: str | None = None
    page_title: str | None = None
    session_expired: bool = False
    verified_at: str | None = None
    note: str | None = None


class DisconnectResponse(BaseModel):
    status: str
    platform: str
    disconnected: bool
    message: str


@router.get("", response_model=AllSessionsResponse)
async def list_browser_sessions():
    """
    Phase 11: Returns authenticated browser session status for LinkedIn and Naukri.
    Public discovery is always the baseline default.
    """
    return BrowserSessionService.get_all_sessions_status()


@router.get("/{platform}/status", response_model=dict[str, Any])
async def get_platform_session_status(platform: str):
    """Inspects storage artifacts and configuration for a specific platform."""
    res = BrowserSessionService.get_session_status(platform)
    if not res.get("supported"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Platform '{platform}' is not supported.",
        )
    return res


@router.post("/{platform}/verify", response_model=VerifySessionResponse)
async def verify_platform_session(platform: str, timeout_seconds: int = Query(20, ge=5, le=60)):
    """Validates if the saved browser session is actively authenticated or expired."""
    res = await BrowserSessionService.verify_platform_session(platform, timeout_seconds=timeout_seconds)
    if res.get("status") == "error":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.get("error"))
    return VerifySessionResponse(**res)


@router.post("/{platform}/disconnect", response_model=DisconnectResponse)
async def disconnect_platform_session(platform: str):
    """Disconnects platform session by safely flushing profile cookies and caches."""
    res = BrowserSessionService.disconnect_session(platform)
    if res.get("status") == "error":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=res.get("error"))
    return DisconnectResponse(**res)
