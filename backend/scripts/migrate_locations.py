"""
One-off migration script to normalize existing jobs' normalized_location
values using the new canonical Indian location taxonomy.
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select, update
from app.database import async_session_factory
from app.models.job import Job
from app.utils.normalization import normalize_location


async def migrate_existing_job_locations():
    async with async_session_factory() as session:
        print("[MIGRATION] Scanning jobs table for un-normalized or legacy locations...")
        stmt = select(Job.id, Job.location, Job.normalized_location)
        res = await session.execute(stmt)
        rows = res.all()
        print(f"[MIGRATION] Found {len(rows)} total jobs in database.")

        updated_count = 0
        for job_id, raw_loc, current_norm in rows:
            new_norm = normalize_location(raw_loc or current_norm)
            if new_norm != current_norm and new_norm != "Unknown":
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(normalized_location=new_norm)
                )
                updated_count += 1

        await session.commit()
        print(f"[MIGRATION] Successfully updated {updated_count} job rows to canonical locations.")


if __name__ == "__main__":
    asyncio.run(migrate_existing_job_locations())
