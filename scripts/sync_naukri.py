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
from app.sources.adapters.naukri import NaukriAdapter
from app.sources.base import JobSearchQuery


async def main(freshness_hours: int = 24):
    print("=" * 68)
    print("💼 NAUKRI LIVE JOB HARVESTER & INGESTION PIPELINE")
    print(f"   Target Window: <={freshness_hours}h")
    print("=" * 68)

    adapter = NaukriAdapter()

    print("\n[1] Checking Naukri live connectivity...")
    healthy = await adapter.health_check()
    print(f"    Health Status: {'ONLINE' if healthy else 'DEGRADED / BLOCKED'}")

    print(f"\n[2] Executing targeted discovery across entry-level software engineering roles (<={freshness_hours}h)...")
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
    print("📊 NAUKRI INGESTION & PIPELINE METRICS")
    print("=" * 68)
    print(f"  • Total Raw Listings Discovered:  {stats.get('total_discovered', 0):>4}")
    print(f"  • Filtered by Freshness (>24h):   {stats.get('filtered_by_freshness', 0):>4}")
    print(f"  • Filtered by Experience Ceiling: {stats.get('filtered_by_experience', 0):>4}")
    print(f"  • Fresh Surviving Postings:       {stats.get('fresh_jobs', 0):>4}")
    print(f"  • Deduplication Reductions:       {stats.get('deduplicated', 0):>4}")
    print(f"  • Canonical Jobs Persisted (DB):  {stats.get('canonical_saved', 0):>4}")
    print(f"  • Existing Jobs Updated:          {stats.get('updated_existing', 0):>4}")
    print("=" * 68)
    print("✓ Naukri live sync completed successfully.\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Naukri Live Job Harvester")
    parser.add_argument(
        "--freshness",
        type=int,
        default=24,
        choices=[1, 4, 8, 12, 16, 24],
        help="Freshness window in hours (1, 4, 8, 12, 16, 24). Default: 24",
    )
    args = parser.parse_args()
    asyncio.run(main(freshness_hours=args.freshness))
