import asyncio
from typing import Any, Sequence
import structlog

from app.config import settings
from app.sources.base import JobSearchQuery, JobSource, RawJob

logger = structlog.get_logger(__name__)


class SourceRegistry:
    """
    Registry coordinating enabled job source adapters.
    Provides parallel search dispatch with error isolation and robust session-isolated
    database sync routines with automatic rollback on platform failures.
    """

    def __init__(self):
        self._sources: dict[str, JobSource] = {}

    def register(self, source: JobSource) -> None:
        self._sources[source.source_name] = source
        logger.info("job_source_registered", name=source.source_name, enabled=source.enabled)

    def get_source(self, name: str) -> JobSource | None:
        return self._sources.get(name)

    def get_enabled_sources(self) -> list[JobSource]:
        return [s for s in self._sources.values() if s.enabled]

    async def search_all(self, query: JobSearchQuery) -> tuple[list[RawJob], dict[str, int]]:
        """
        Executes parallel search across all enabled sources with error isolation.
        A failure in one source does not abort others.
        """
        enabled = self.get_enabled_sources()
        if not enabled:
            logger.warning("no_job_sources_enabled")
            return [], {}

        async def _run_source(src: JobSource) -> tuple[str, list[RawJob]]:
            try:
                results = await src.search(query)
                return src.source_name, results
            except Exception as e:
                logger.error("source_search_failed", source=src.source_name, error=str(e))
                return src.source_name, []

        tasks = [_run_source(s) for s in enabled]
        completed = await asyncio.gather(*tasks)

        all_raw: list[RawJob] = []
        source_counts: dict[str, int] = {}
        for src_name, items in completed:
            source_counts[src_name] = len(items)
            all_raw.extend(items)

        logger.info(
            "multi_source_search_completed",
            total_discovered=len(all_raw),
            counts=source_counts,
        )
        return all_raw, source_counts

    async def sync_source_isolated(
        self,
        source: JobSource,
        db: Any,
        ingestion_service: Any,
        query: JobSearchQuery | None = None,
    ) -> dict[str, Any]:
        """
        Executes ingestion for a single source within an isolated transaction boundary.
        If any exception occurs (e.g. rate limit, anti-bot, network timeout), the database
        session is immediately rolled back to prevent dirty reads or uncommitted state.
        """
        from app.core.lock import redis_lock

        # Acquire per-source distributed lock (5 min timeout) to avoid concurrent worker collisions
        async with redis_lock(f"sync:{source.source_name}", timeout_seconds=300):
            try:
                if hasattr(source, "reset_metrics"):
                    source.reset_metrics()
                stats = await ingestion_service.ingest_source(db, source, query)
                src_status = getattr(source, "status", "ok")
                metrics = source.get_metrics().model_dump() if hasattr(source, "get_metrics") else {}
                stats["metrics"] = metrics
                stats["duration_ms"] = metrics.get("duration_ms", 0.0)
                stats["retries_count"] = metrics.get("retries_count", 0)

                if src_status == "blocked":
                    stats["status"] = "blocked"
                    stats["error"] = getattr(source, "last_error", None) or "Source blocked by upstream perimeter"
                    stats["error_category"] = getattr(source, "last_error_category", "rate_limit_block")
                elif src_status == "failed":
                    stats["status"] = "failed"
                    stats["error"] = getattr(source, "last_error", None) or "Source search failed"
                    stats["error_category"] = getattr(source, "last_error_category", "fatal")
                else:
                    stats["status"] = "success"
                return stats
            except Exception as e:
                logger.error(
                    "source_sync_isolated_failed_rolling_back",
                    source=source.source_name,
                    error=str(e),
                )
                if hasattr(db, "rollback"):
                    await db.rollback()
                raise

    async def sync_all_isolated(
        self,
        db: Any,
        ingestion_service: Any,
        query: JobSearchQuery | None = None,
    ) -> dict[str, Any]:
        """
        Syncs all enabled sources sequentially with per-source transaction isolation.
        A failure in any individual source (such as LinkedIn hitting a 429 block) rolls
        back only that source's transactions without terminating sync for remaining adapters.
        """
        enabled = self.get_enabled_sources()
        aggregated_stats: dict[str, Any] = {
            "status": "success",
            "total_discovered": 0,
            "filtered_by_freshness": 0,
            "fresh_jobs": 0,
            "filtered_by_experience": 0,
            "eligible_candidates": 0,
            "deduplicated": 0,
            "canonical_saved": 0,
            "updated_existing": 0,
            "saved_jobs": 0,
            "saved_internships": 0,
            "sources_synced": [],
            "sources": {},
            "failed_sources": [],
        }

        for src in enabled:
            src_status = "success"
            src_err = None
            src_err_cat = None
            stats = {}
            try:
                stats = await self.sync_source_isolated(src, db, ingestion_service, query)
                aggregated_stats["sources_synced"].append(src.source_name)
                for key in (
                    "total_discovered",
                    "filtered_by_freshness",
                    "fresh_jobs",
                    "filtered_by_experience",
                    "eligible_candidates",
                    "deduplicated",
                    "canonical_saved",
                    "updated_existing",
                    "saved_jobs",
                    "saved_internships",
                ):
                    aggregated_stats[key] += stats.get(key, 0)
                if stats.get("status") == "blocked":
                    src_status = "blocked"
                    src_err = stats.get("error")
                    src_err_cat = stats.get("error_category", "rate_limit_block")
                elif stats.get("status") == "failed":
                    src_status = "failed"
                    src_err = stats.get("error")
                    src_err_cat = stats.get("error_category", "fatal")
            except Exception as e:
                logger.error("source_sync_isolated_aborted", source=src.source_name, error=str(e))
                aggregated_stats["failed_sources"].append({"source": src.source_name, "error": str(e)})
                if "403" in str(e) or "429" in str(e) or "block" in str(e).lower():
                    src_status = "blocked"
                    src_err_cat = "rate_limit_block"
                else:
                    src_status = "failed"
                    src_err_cat = "transient_network" if "timeout" in str(e).lower() else "fatal"
                src_err = str(e)

            report = {
                "status": src_status,
                "discovered": stats.get("total_discovered", 0),
                "accepted": stats.get("canonical_saved", 0) + stats.get("updated_existing", 0),
                "duration_ms": stats.get("duration_ms", 0.0),
                "retries": stats.get("retries_count", 0),
            }
            if src_err:
                report["error"] = src_err
            if src_err_cat:
                report["error_category"] = src_err_cat
            aggregated_stats["sources"][src.source_name] = report

        # Determine overall status
        statuses = [s["status"] for s in aggregated_stats["sources"].values()]
        if all(s == "success" for s in statuses):
            aggregated_stats["status"] = "success"
        elif all(s == "blocked" for s in statuses):
            aggregated_stats["status"] = "blocked"
        elif any(s == "success" for s in statuses):
            aggregated_stats["status"] = "partial_success"
        else:
            aggregated_stats["status"] = "failed"

        return aggregated_stats

    async def health_check_all(self) -> dict[str, bool]:
        """Performs health check on all registered sources."""
        status = {}
        for name, src in self._sources.items():
            try:
                status[name] = await src.health_check()
            except Exception:
                status[name] = False
        return status


_registry: SourceRegistry | None = None


def reset_registry() -> None:
    """Resets global registry instance (used for testing and dynamic config reload)."""
    global _registry
    _registry = None


def get_source_registry() -> SourceRegistry:
    """Initializes and returns the global SourceRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = SourceRegistry()

        # Register Sample adapter (testing only)
        if getattr(settings, "SOURCE_SAMPLE_ENABLED", False):
            try:
                from app.sources.adapters.sample import SampleJobAdapter
                _registry.register(SampleJobAdapter())
            except Exception as e:
                logger.warning("sample_adapter_registration_failed", error=str(e))

        # Register Internshala adapter
        if getattr(settings, "SOURCE_INTERNSHALA_ENABLED", True):
            try:
                from app.sources.adapters.internshala import InternshalaAdapter
                _registry.register(InternshalaAdapter())
            except Exception as e:
                logger.warning("internshala_adapter_registration_failed", error=str(e))

        # Register Naukri adapter
        if getattr(settings, "SOURCE_NAUKRI_ENABLED", True):
            try:
                from app.sources.adapters.naukri import NaukriAdapter
                _registry.register(NaukriAdapter())
            except Exception as e:
                logger.warning("naukri_adapter_registration_failed", error=str(e))

        # Register LinkedIn adapter (SOURCE_LINKEDIN_ENABLED=true)
        if getattr(settings, "SOURCE_LINKEDIN_ENABLED", True):
            try:
                from app.sources.adapters.linkedin import LinkedInAdapter
                _registry.register(LinkedInAdapter())
            except Exception as e:
                logger.warning("linkedin_adapter_registration_failed", error=str(e))

    return _registry


