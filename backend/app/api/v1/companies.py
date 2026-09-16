from fastapi import APIRouter, Depends, Query
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import Job

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("/suggest", response_model=list[str])
async def suggest_companies(
    db: AsyncSession = Depends(get_db),
    q: str = Query("", min_length=0, max_length=100),
    limit: int = Query(8, ge=1, le=25),
):
    """Return distinct company names from ingested jobs matching query."""
    stmt = (
        select(distinct(Job.company_name))
        .where(Job.company_name.ilike(f"%{q.strip()}%"))
        .order_by(Job.company_name)
        .limit(limit)
    )
    res = await db.execute(stmt)
    return [name for (name,) in res.all() if name]