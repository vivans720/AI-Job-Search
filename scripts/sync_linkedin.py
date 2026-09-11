#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

# Add backend directory
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.services.job_ingestion_service import JobIngestionService
from app.sources.adapters.linkedin import LinkedInAdapter
from app.sources.base import JobSearchQuery


async def main(freshness_hours: int = 24):
    print("=" * 68)
    print("💼 LINKEDIN LIVE JOB HARVESTER & INGESTION PIPELINE")
    print(f"   Target Window: <={freshness_hours}h")
    print("=" * 68)

    adapter = LinkedInAdapter()

    print("\n[1] Checking LinkedIn live connectivity...")
    healthy = await adapter.health_check()
    print(f"    Health Status: {'ONLINE' if healthy else 'DEGRADED / BLOCKED'}")

    print(f"\n[2] Executing dual discovery across entry-level roles (<={freshness_hours}h IST)...")
    query = JobSearchQuery(
        skills=["javascript", "typescript", "react", "node.js", "python"],
        freshness_hours=freshness_hours,
        include_remote=True,
        include_jobs=True,
        include_internships=True,
        experience_max=2,
        limit=50,
    )

    ingestion_service = JobIngestionService()
    async with async_session_factory() as db:
        stats = await ingestion_service.ingest_source(db, adapter, query)

    print("\n" + "=" * 68)
    print("📊 LINKEDIN INGESTION & PIPELINE METRICS")
    print("=" * 68)
    print(f"  • Total Raw Listings Discovered:  {stats.get('total_discovered', 0):>4}")
    print(f"  • Filtered by Freshness (>24h):   {stats.get('filtered_by_freshness', 0):>4}")
    print(f"  • Filtered by Experience Ceiling: {stats.get('filtered_by_experience', 0):>4}")
    print(f"  • Fresh Surviving Postings:       {stats.get('fresh_jobs', 0):>4}")
    print(f"  • Deduplication Reductions:       {stats.get('deduplicated', 0):>4}")
    print(f"  • Canonical Jobs Persisted (DB):  {stats.get('canonical_saved', 0):>4}")
    print(f"  • Existing Jobs Updated:          {stats.get('updated_existing', 0):>4}")
    print("=" * 68)
    print("✓ LinkedIn live sync completed successfully.\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LinkedIn Live Job Harvester")
    parser.add_argument(
        "--freshness",
        type=int,
        default=24,
        choices=[1, 4, 8, 12, 16, 24],
        help="Freshness window in hours (1, 4, 8, 12, 16, 24). Default: 24",
    )
    args = parser.parse_args()
    asyncio.run(main(freshness_hours=args.freshness))
