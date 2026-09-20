import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.notification import (
    CreateDailyDigestRequest,
    DailyDigestListItem,
    DailyDigestResponse,
    ScheduledSearchTriggerRequest,
)
from app.services.scheduled_search_service import ScheduledSearchService
from app.services.user_service import get_or_create_default_user

router = APIRouter(prefix="/digests", tags=["Daily Digests"])


@router.get("", response_model=list[DailyDigestListItem])
async def list_daily_digests(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """List candidate daily job digests in reverse chronological order."""
    user = await get_or_create_default_user(db)
    digests = await ScheduledSearchService.get_recent_digests(db, user.id, limit=limit)
    items = []
    for d in digests:
        preview = d.summary[:200] + "..." if len(d.summary) > 200 else d.summary
        items.append(
            DailyDigestListItem(
                id=d.id,
                digest_date=d.digest_date,
                summary_preview=preview,
                job_count=d.total_found,
                strong_matches_count=d.strong_matches_count,
                status=d.status,
                created_at=d.created_at,
            )
        )
    return items


@router.get("/latest", response_model=DailyDigestResponse)
async def get_latest_digest(
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the most recent daily job digest briefing."""
    user = await get_or_create_default_user(db)
    digest = await ScheduledSearchService.get_latest_digest(db, user.id)
    if not digest:
        raise HTTPException(status_code=404, detail="No daily digests found for candidate.")
    return digest


@router.post("", response_model=DailyDigestResponse, status_code=status.HTTP_201_CREATED)
async def create_digest(
    request: CreateDailyDigestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Publish a daily job digest manually (e.g. from Hermes Agent)."""
    user = await get_or_create_default_user(db)
    digest = await ScheduledSearchService.create_digest_manual(
        db=db,
        user_id=user.id,
        summary=request.summary,
        job_ids=request.job_ids,
        status=request.status,
        metadata_info=request.metadata_info,
    )
    return digest


@router.post("/run-scheduled-search")
async def trigger_scheduled_job_search(
    request: ScheduledSearchTriggerRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger an immediate autonomous scheduled job search run."""
    user = await get_or_create_default_user(db)
    result = await ScheduledSearchService.run_scheduled_job_search(
        db=db,
        user_id=user.id,
        freshness_hours=request.freshness_hours,
        match_threshold_override=request.match_threshold,
        dry_run=request.dry_run,
    )
    return result
