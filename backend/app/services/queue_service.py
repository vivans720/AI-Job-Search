import json
import time
import uuid
import structlog
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from app.core.redis import get_redis

logger = structlog.get_logger(__name__)

DEFAULT_QUEUE_NAME = "jobs:queue"
DLQ_NAME = "jobs:dlq"


class TaskJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    attempts: int = 0
    max_retries: int = 3
    created_at: float = Field(default_factory=time.time)
    error: Optional[str] = None


class QueueService:
    def __init__(self, queue_name: str = DEFAULT_QUEUE_NAME, dlq_name: str = DLQ_NAME):
        self.queue_name = queue_name
        self.dlq_name = dlq_name

    async def enqueue(self, task_type: str, payload: Dict[str, Any], max_retries: int = 3) -> Optional[str]:
        redis = await get_redis()
        if not redis:
            logger.warning("queue_unavailable_cannot_enqueue", task_type=task_type)
            return None

        job = TaskJob(
            task_type=task_type,
            payload=payload,
            max_retries=max_retries,
        )
        try:
            await redis.lpush(self.queue_name, job.model_dump_json())
            await self.set_job_status(job.id, "queued", task_type=task_type)
            logger.info("job_enqueued", job_id=job.id, task_type=task_type)
            return job.id
        except Exception as e:
            logger.error("job_enqueue_failed", task_type=task_type, error=str(e))
            return None

    async def dequeue(self, timeout_seconds: int = 2) -> Optional[TaskJob]:
        redis = await get_redis()
        if not redis:
            return None

        try:
            # BRPOP returns tuple: (queue_name, item)
            item = await redis.brpop(self.queue_name, timeout=timeout_seconds)
            if item:
                _, raw_data = item
                data = json.loads(raw_data)
                return TaskJob(**data)
            return None
        except Exception as e:
            logger.debug("job_dequeue_error", error=str(e))
            return None

    async def fail_job(self, job: TaskJob, error_message: str) -> None:
        redis = await get_redis()
        if not redis:
            return

        job.attempts += 1
        job.error = error_message

        try:
            if job.attempts >= job.max_retries:
                await redis.lpush(self.dlq_name, job.model_dump_json())
                logger.warning("job_moved_to_dlq", job_id=job.id, task_type=job.task_type, attempts=job.attempts)
            else:
                await redis.lpush(self.queue_name, job.model_dump_json())
                logger.info("job_requeued_for_retry", job_id=job.id, task_type=job.task_type, attempt=job.attempts)
        except Exception as e:
            logger.error("job_fail_handling_error", job_id=job.id, error=str(e))

    async def set_job_status(
        self,
        job_id: str,
        status: str,
        task_type: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        progress: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        ttl_seconds: int = 86400,
    ) -> None:
        redis = await get_redis()
        if not redis:
            return

        status_key = f"job:{job_id}:status"
        try:
            existing_raw = await redis.get(status_key)
            data: Dict[str, Any] = json.loads(existing_raw) if existing_raw else {
                "job_id": job_id,
                "task_type": task_type,
                "created_at": time.time(),
            }
            data["status"] = status
            data["updated_at"] = time.time()
            if task_type:
                data["task_type"] = task_type
            if progress is not None:
                data["progress"] = progress
            if result is not None:
                data["result"] = result
            if error is not None:
                data["error"] = error
            if status == "completed":
                data["completed_at"] = time.time()

            await redis.set(status_key, json.dumps(data), ex=ttl_seconds)
        except Exception as e:
            logger.debug("set_job_status_error", job_id=job_id, error=str(e))

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        redis = await get_redis()
        if not redis:
            return None

        status_key = f"job:{job_id}:status"
        try:
            val = await redis.get(status_key)
            if val:
                return json.loads(val)
            return None
        except Exception as e:
            logger.debug("get_job_status_error", job_id=job_id, error=str(e))
            return None

    async def cancel_job(self, job_id: str) -> bool:
        redis = await get_redis()
        if not redis:
            return False

        try:
            cancel_key = f"job:{job_id}:cancel_requested"
            await redis.set(cancel_key, "1", ex=86400)
            await self.set_job_status(job_id, "cancelled", error="Cancelled by user")
            logger.info("job_cancellation_requested", job_id=job_id)
            return True
        except Exception as e:
            logger.error("job_cancellation_failed", job_id=job_id, error=str(e))
            return False

    async def is_job_cancelled(self, job_id: str) -> bool:
        redis = await get_redis()
        if not redis:
            return False

        try:
            val = await redis.get(f"job:{job_id}:cancel_requested")
            return bool(val)
        except Exception:
            return False


task_queue = QueueService()
