import asyncio
import signal
import structlog
import redis.asyncio as aioredis
from app.config import settings

logger = structlog.get_logger(__name__)

should_exit = False


def handle_exit_signal(sig, frame):
    global should_exit
    logger.info("worker_signal_received", signal=sig)
    should_exit = True


async def process_sync_source_job(job, task_queue):
    from app.database import async_session_factory
    from app.services.job_ingestion_service import JobIngestionService
    from app.sources.base import JobSearchQuery
    from app.sources.registry import get_source_registry
    from app.core.cache import invalidate_cache

    source_clean = str(job.payload.get("source", "all")).strip().lower()
    freshness_hours = int(job.payload.get("freshness_hours", 24))
    allowed_freshness = [1, 4, 8, 12, 16, 24]
    if freshness_hours not in allowed_freshness:
        freshness_hours = min(allowed_freshness, key=lambda x: abs(x - freshness_hours))

    registry = get_source_registry()
    sources_to_sync = []
    if source_clean in ["all", "*", ""]:
        sources_to_sync = registry.get_enabled_sources()
    else:
        src = registry.get_source(source_clean)
        if not src:
            raise ValueError(f"Source '{source_clean}' not found in registry")
        sources_to_sync = [src]

    target_skills = ["javascript", "typescript", "react", "node.js", "python"]
    ingestion_service = JobIngestionService()
    query = JobSearchQuery(
        skills=target_skills,
        freshness_hours=freshness_hours,
        experience_max=2,
        include_jobs=True,
        include_internships=True,
    )

    aggregated_stats = {
        "status": "success",
        "source": source_clean,
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
        "ai_extracted_skills": 0,
        "normalized_skills": 0,
        "embeddings_generated": 0,
        "matches_evaluated": 0,
        "sources_synced": [],
        "sources": {},
        "failed_sources": [],
        "duplicates_log": [],
    }

    # Track incremental progress for UI/polling
    progress_tracker = {
        s.source_name: {
            "status": "pending",
            "discovered": 0,
            "saved": 0,
            "updated": 0,
            "duplicates": 0,
            "rejected": 0,
            "skills": 0,
            "embeddings": 0,
        }
        for s in sources_to_sync
    }
    await task_queue.set_job_status(job.id, "running", task_type=job.task_type, progress=progress_tracker)

    async with async_session_factory() as db:
        for src in sources_to_sync:
            progress_tracker[src.source_name]["status"] = "running"
            await task_queue.set_job_status(job.id, "running", task_type=job.task_type, progress=progress_tracker)

            src_status = "success"
            src_err = None
            stats = {}
            try:
                stats = await registry.sync_source_isolated(src, db, ingestion_service, query)
                aggregated_stats["sources_synced"].append(src.source_name)
                for k in [
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
                    "ai_extracted_skills",
                    "normalized_skills",
                    "embeddings_generated",
                    "matches_evaluated",
                ]:
                    aggregated_stats[k] += stats.get(k, 0)
                if stats.get("status") == "blocked":
                    src_status = "blocked"
                    src_err = stats.get("error")
                elif stats.get("status") == "failed":
                    src_status = "failed"
                    src_err = stats.get("error")
            except Exception as e:
                logger.error("worker_sync_source_isolated_failed", source=src.source_name, error=str(e))
                aggregated_stats["failed_sources"].append({"source": src.source_name, "error": str(e)})
                if "403" in str(e) or "block" in str(e).lower():
                    src_status = "blocked"
                else:
                    src_status = "failed"
                src_err = str(e)

            metrics_data = stats.get("metrics", {})
            report = {
                "status": src_status,
                "discovered": stats.get("total_discovered", 0),
                "accepted": stats.get("canonical_saved", 0) + stats.get("updated_existing", 0),
                "duration_ms": stats.get("duration_ms", 0.0),
                "retries": stats.get("retries_count", 0),
                "skills": stats.get("ai_extracted_skills", 0) + stats.get("normalized_skills", 0),
                "embeddings": stats.get("embeddings_generated", 0),
                "matches": stats.get("matches_evaluated", 0),
                "queries": metrics_data.get("queries_count", 0),
                "pages": metrics_data.get("pages_count", 0),
                "hydrations": metrics_data.get("hydration_requests_count", 0),
                "rate_limit_wait_ms": metrics_data.get("rate_limit_wait_ms", 0.0),
                "persistence_duration_ms": stats.get("persistence_duration_ms", 0.0),
                "match_duration_ms": stats.get("match_duration_ms", 0.0),
            }
            if src_err:
                report["error"] = src_err
            if stats.get("error_category"):
                report["error_category"] = stats.get("error_category")
            aggregated_stats["sources"][src.source_name] = report

            logger.info(
                "source_sync_summary",
                source=src.source_name,
                status=src_status,
                queries_executed=metrics_data.get("queries_count", 0),
                pages_fetched=metrics_data.get("pages_count", 0),
                candidates_discovered=stats.get("total_discovered", 0),
                fresh_candidates_accepted=stats.get("fresh_jobs", 0),
                fresh_candidates_rejected=stats.get("filtered_by_freshness", 0),
                hydration_count=metrics_data.get("hydration_requests_count", 0),
                rate_limit_wait_ms=round(metrics_data.get("rate_limit_wait_ms", 0.0), 2),
                total_duration_ms=round(stats.get("duration_ms", 0.0), 2),
                persistence_duration_ms=round(stats.get("persistence_duration_ms", 0.0), 2),
            )


            progress_tracker[src.source_name] = {
                "status": src_status,
                "discovered": stats.get("total_discovered", 0),
                "saved": stats.get("canonical_saved", 0),
                "updated": stats.get("updated_existing", 0),
                "duplicates": stats.get("deduplicated", 0),
                "rejected": stats.get("filtered_by_freshness", 0) + stats.get("filtered_by_validation", 0),
                "skills": stats.get("ai_extracted_skills", 0) + stats.get("normalized_skills", 0),
                "embeddings": stats.get("embeddings_generated", 0),
                "queries": metrics_data.get("queries_count", 0),
                "pages": metrics_data.get("pages_count", 0),
                "rate_limit_wait_ms": metrics_data.get("rate_limit_wait_ms", 0.0),
            }
            await task_queue.set_job_status(job.id, "running", task_type=job.task_type, progress=progress_tracker)

    if aggregated_stats["sources"]:
        statuses = [s["status"] for s in aggregated_stats["sources"].values()]
        if all(s == "success" for s in statuses):
            aggregated_stats["status"] = "success"
        elif all(s == "blocked" for s in statuses):
            aggregated_stats["status"] = "blocked"
        elif any(s == "success" for s in statuses):
            aggregated_stats["status"] = "partial_success"
        else:
            aggregated_stats["status"] = "failed"
    else:
        aggregated_stats["status"] = "failed"

    # Invalidate cached queries on fresh sync
    await invalidate_cache("stats:*")
    await invalidate_cache("query:*")

    return aggregated_stats


async def run_worker():
    global should_exit
    signal.signal(signal.SIGTERM, handle_exit_signal)
    signal.signal(signal.SIGINT, handle_exit_signal)

    logger.info("worker_starting", redis_url=settings.REDIS_URL)

    redis_client = None
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, socket_timeout=3.0)
        await redis_client.ping()
        logger.info("worker_redis_connected")
    except Exception as e:
        logger.warning("worker_redis_connection_failed", error=str(e))

    try:
        from app.database import init_pgvector
        await init_pgvector()
        logger.info("worker_pgvector_and_schema_verified")
    except Exception as e:
        logger.warning("worker_schema_init_warning", error=str(e))

    logger.info("worker_ready_for_jobs")

    from app.services.queue_service import task_queue, TaskJob

    last_heartbeat = 0.0

    while not should_exit:
        now = asyncio.get_event_loop().time()
        if redis_client and (now - last_heartbeat) >= 15.0:
            try:
                await redis_client.set("worker:heartbeat", str(now), ex=60)
                last_heartbeat = now
            except Exception as e:
                logger.debug("worker_heartbeat_error", error=str(e))

        # Check for task in queue
        try:
            job: TaskJob = await task_queue.dequeue(timeout_seconds=2)
            if job:
                logger.info("worker_processing_job", job_id=job.id, task_type=job.task_type)
                await task_queue.set_job_status(job.id, "running", task_type=job.task_type)
                try:
                    if job.task_type == "ping":
                        res = {"pong": True, "payload": job.payload}
                        logger.info("worker_job_ping_processed", payload=job.payload)
                        await task_queue.set_job_status(job.id, "completed", task_type=job.task_type, result=res)
                    elif job.task_type == "sync_source":
                        result_stats = await process_sync_source_job(job, task_queue)
                        await task_queue.set_job_status(
                            job.id,
                            "completed",
                            task_type=job.task_type,
                            result=result_stats,
                        )
                    elif job.task_type == "enrich_job_intelligence":
                        from app.database import async_session_factory
                        from app.intelligence.extractors import enrich_job_record_llm
                        import uuid as py_uuid
                        job_id_str = job.payload.get("job_id")
                        if not job_id_str:
                            raise ValueError("job_id required for intelligence enrichment")
                        parsed_jid = py_uuid.UUID(job_id_str)
                        async with async_session_factory() as db:
                            enrichment = await enrich_job_record_llm(parsed_jid, db)
                            res = enrichment.model_dump() if enrichment else {"status": "job_not_found"}
                            await task_queue.set_job_status(
                                job.id,
                                "completed",
                                task_type=job.task_type,
                                result=res,
                            )
                    else:
                        logger.info("worker_unknown_job_type", task_type=job.task_type)
                        await task_queue.set_job_status(
                            job.id,
                            "completed",
                            task_type=job.task_type,
                            result={"note": "unhandled_job_type"},
                        )
                    logger.info("worker_job_success", job_id=job.id)
                except Exception as task_err:
                    logger.error("worker_job_failed", job_id=job.id, error=str(task_err))
                    await task_queue.set_job_status(
                        job.id,
                        "failed",
                        task_type=job.task_type,
                        error=str(task_err),
                    )
                    await task_queue.fail_job(job, str(task_err))
        except Exception as e:
            logger.debug("worker_dequeue_loop_error", error=str(e))

        await asyncio.sleep(0.1)

    logger.info("worker_shutting_down")
    if redis_client:
        await redis_client.aclose()
    logger.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())

