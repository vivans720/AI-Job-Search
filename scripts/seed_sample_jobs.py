import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import async_session_factory
from app.services.job_ingestion_service import JobIngestionService
from app.sources.adapters.sample import SampleJobAdapter
from app.sources.base import JobSearchQuery


async def seed():
    print("🚀 Initializing Sample Job Engine Ingestion Pipeline...")
    adapter = SampleJobAdapter()
    if not await adapter.health_check():
        print("❌ Error: Sample dataset file not found.")
        sys.exit(1)

    ingestion_service = JobIngestionService()

    async with async_session_factory() as db:
        result = await ingestion_service.ingest_source(db, adapter, JobSearchQuery(freshness_hours=24))

    print("\n✅ Ingestion Results:")
    print(f"   • Total Discovered:       {result['total_discovered']}")
    print(f"   • Stale / Low Confidence: {result['filtered_by_freshness']} filtered out")
    print(f"   • Fresh Within 24h:       {result['fresh_jobs']}")
    print(f"   • Duplicates Merged:      {result['deduplicated']}")
    print(f"   • Canonical Jobs Saved:   {result['canonical_saved']}")

    if result["duplicates_log"]:
        print("\n🔍 Deduplication Audit Sample:")
        for d in result["duplicates_log"][:3]:
            print(f"   - Merged '{d['duplicate_title']}' ({d['duplicate_source']}) into '{d['canonical_title']}' ({d['canonical_source']}) via {d['reason']}")

    print("\n🎉 Sample Job Engine successfully populated database with fresh Indian tech opportunities.")


if __name__ == "__main__":
    asyncio.run(seed())
