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
from app.sources.adapters.internshala import InternshalaAdapter
from app.sources.base import JobSearchQuery


async def main(freshness_hours: int = 24):
    print("=" * 68)
    print("🎓 INTERNSHALA LIVE MULTI-CATEGORY HARVESTER & PIPELINE")
    print(f"   Target Window: <={freshness_hours}h")
    print("=" * 68)

    adapter = InternshalaAdapter()

    print("\n[1] Checking Internshala live connectivity...")
    healthy = await adapter.health_check()
    print(f"    Health Status: {'ONLINE (200 OK)' if healthy else 'DEGRADED / BLOCKED'}")
    if not healthy:
        print("❌ Cannot proceed with degraded connection.")
        return

    print(f"\n[2] Executing multi-category discovery & pagination across tech domains (<={freshness_hours}h)...")
    query = JobSearchQuery(
        skills=["javascript", "typescript", "react", "node.js", "python"],
        freshness_hours=freshness_hours,
        include_remote=True,
        include_jobs=True,
        include_internships=True,
        experience_max=2,
    )

    ingestion_service = JobIngestionService()
    async with async_session_factory() as db:
        stats = await ingestion_service.ingest_source(db, adapter, query)

    # Display per-category metrics partitioned by Jobs and Internships
    if hasattr(adapter, "last_category_metrics") and adapter.last_category_metrics:
        jobs_meta = adapter.last_category_metrics.get("jobs", {})
        internships_meta = adapter.last_category_metrics.get("internships", {})

        print("\n" + "-" * 68)
        print("📂 CATEGORY-LEVEL DISCOVERY METRICS")
        print("-" * 68)
        if jobs_meta:
            print("  [Jobs (/jobs/...)]")
            for cat, m in jobs_meta.items():
                print(f"    • {cat:<24} Discovered: {m['discovered']:<3} | Fresh: {m['fresh']:<2}")
        if internships_meta:
            print("  [Internships (/internships/...)]")
            for cat, m in internships_meta.items():
                print(f"    • {cat:<24} Discovered: {m['discovered']:<3} | Fresh: {m['fresh']:<2}")

    print("\n" + "=" * 68)
    print("📊 PIPELINE FUNNEL OBSERVABILITY")
    print("=" * 68)
    print(f" • [Stage 1] Raw Discovered:       {stats['total_discovered']} listings")
    print(f" • [Stage 2] Excluded (>24h/Stale): {stats['filtered_by_freshness']} listings")
    print(f" • [Stage 3] Fresh Candidates:      {stats.get('fresh_jobs', 0)} listings")
    print(f" • [Stage 4] Experience Filtered:  {stats.get('filtered_by_experience', 0)} listings (>2y / Senior)")
    print(f" • [Stage 5] Eligible Candidates:   {stats.get('eligible_candidates', 0)} listings")
    print(f" • [Stage 6] Duplicates Merged:     {stats.get('deduplicated', 0)} listings")
    print(f" • [Stage 7] Canonical Newly Saved: {stats.get('canonical_saved', 0)} listings (Jobs: {stats.get('saved_jobs', 0)} | Internships: {stats.get('saved_internships', 0)})")
    print(f" • [Stage 8] Existing Refreshed:    {stats.get('updated_existing', 0)} listings")
    print("=" * 68)
    print("✓ Internshala multi-category live sync completed successfully.\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Internshala Live Job Harvester")
    parser.add_argument(
        "--freshness",
        type=int,
        default=24,
        choices=[1, 4, 8, 12, 16, 24],
        help="Freshness window in hours (1, 4, 8, 12, 16, 24). Default: 24",
    )
    args = parser.parse_args()
    asyncio.run(main(freshness_hours=args.freshness))
