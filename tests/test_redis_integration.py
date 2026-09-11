import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.core.redis import init_redis_pool, close_redis_pool, get_redis
from app.core.lock import redis_lock, RedisLockError
from app.core.rate_limiter import check_rate_limit
from app.core.cache import cached, invalidate_cache, make_cache_key
from app.services.queue_service import QueueService, TaskJob


@pytest.mark.asyncio
async def test_make_cache_key():
    k1 = make_cache_key("test", 1, a=2)
    k2 = make_cache_key("test", 1, a=2)
    k3 = make_cache_key("test", 2, a=2)
    assert k1 == k2
    assert k1 != k3
    assert k1.startswith("cache:test:")


@pytest.mark.asyncio
async def test_cache_decorator_fallback_when_no_redis():
    with patch("app.core.cache.get_redis", return_value=None):
        call_count = 0

        @cached(ttl_seconds=60, prefix="test")
        async def my_func(x):
            nonlocal call_count
            call_count += 1
            return {"data": x * 2}

        res1 = await my_func(5)
        res2 = await my_func(5)
        assert res1 == {"data": 10}
        assert res2 == {"data": 10}
        assert call_count == 2


@pytest.mark.asyncio
async def test_cache_decorator_with_mock_redis():
    fake_store = {}
    mock_redis = AsyncMock()

    async def mock_get(key):
        return fake_store.get(key)

    async def mock_set(key, val, ex=None):
        fake_store[key] = val
        return True

    mock_redis.get.side_effect = mock_get
    mock_redis.set.side_effect = mock_set

    with patch("app.core.cache.get_redis", return_value=mock_redis):
        call_count = 0

        @cached(ttl_seconds=60, prefix="test_calc")
        async def calc(n):
            nonlocal call_count
            call_count += 1
            return {"val": n + 100}

        res1 = await calc(5)
        assert res1 == {"val": 105}
        assert call_count == 1

        res2 = await calc(5)
        assert res2 == {"val": 105}
        assert call_count == 1


@pytest.mark.asyncio
async def test_redis_lock_lifecycle_acquired_and_released():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True
    mock_redis.eval.return_value = 1

    with patch("app.core.lock.get_redis", return_value=mock_redis):
        async with redis_lock("test_sync", timeout_seconds=10) as acquired:
            assert acquired is True
            mock_redis.set.assert_called_once()

        mock_redis.eval.assert_called_once()


@pytest.mark.asyncio
async def test_redis_lock_timeout_fails():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = None

    with patch("app.core.lock.get_redis", return_value=mock_redis):
        with pytest.raises(RedisLockError):
            async with redis_lock("locked_resource", max_wait_seconds=0.1, retry_interval=0.05):
                pass


@pytest.mark.asyncio
async def test_rate_limiter_lua_eval():
    mock_redis = AsyncMock()
    mock_redis.eval.return_value = [1, 29]

    with patch("app.core.rate_limiter.get_redis", return_value=mock_redis):
        allowed, rem = await check_rate_limit("user:123", limit=30, window_seconds=60)
        assert allowed is True
        assert rem == 29

    mock_redis.eval.return_value = [0, 0]
    with patch("app.core.rate_limiter.get_redis", return_value=mock_redis):
        allowed, rem = await check_rate_limit("user:123", limit=30, window_seconds=60)
        assert allowed is False
        assert rem == 0


@pytest.mark.asyncio
async def test_queue_enqueue_and_dequeue():
    queue = QueueService(queue_name="test:queue", dlq_name="test:dlq")
    mock_redis = AsyncMock()

    stored_items = []

    async def mock_lpush(name, item):
        stored_items.append(item)
        return len(stored_items)

    async def mock_brpop(name, timeout=2):
        if stored_items:
            item = stored_items.pop(0)
            return (name, item)
        return None

    mock_redis.lpush.side_effect = mock_lpush
    mock_redis.brpop.side_effect = mock_brpop
    mock_redis.llen.return_value = 1

    with patch("app.services.queue_service.get_redis", return_value=mock_redis):
        job_id = await queue.enqueue("sync_source", {"source": "linkedin"})
        assert job_id is not None
        assert len(stored_items) == 1

        task = await queue.dequeue()
        assert task is not None
        assert task.id == job_id
        assert task.task_type == "sync_source"
        assert task.payload == {"source": "linkedin"}


@pytest.mark.asyncio
async def test_queue_failure_moves_to_dlq_after_max_retries():
    queue = QueueService(queue_name="test:queue", dlq_name="test:dlq")
    mock_redis = AsyncMock()
    dlq_items = []
    requeued_items = []

    async def mock_lpush(name, item):
        if name == "test:dlq":
            dlq_items.append(item)
        else:
            requeued_items.append(item)
        return 1

    mock_redis.lpush.side_effect = mock_lpush

    with patch("app.services.queue_service.get_redis", return_value=mock_redis):
        job = TaskJob(task_type="crawl", attempts=0, max_retries=2)
        # Attempt 1 -> requeue
        await queue.fail_job(job, "network error")
        assert len(requeued_items) == 1
        assert len(dlq_items) == 0

        # Attempt 2 -> moves to DLQ
        await queue.fail_job(job, "fatal error")
        assert len(dlq_items) == 1


@pytest.mark.asyncio
async def test_queue_job_status_tracking():
    queue = QueueService(queue_name="test:queue", dlq_name="test:dlq")
    mock_redis = AsyncMock()
    store = {}

    async def mock_set(key, val, ex=None):
        store[key] = val
        return True

    async def mock_get(key):
        return store.get(key)

    mock_redis.set.side_effect = mock_set
    mock_redis.get.side_effect = mock_get

    with patch("app.services.queue_service.get_redis", return_value=mock_redis):
        await queue.set_job_status("job-123", "queued", task_type="sync_source")
        status = await queue.get_job_status("job-123")
        assert status is not None
        assert status["status"] == "queued"
        assert status["task_type"] == "sync_source"

        await queue.set_job_status("job-123", "completed", result={"saved": 5})
        status_done = await queue.get_job_status("job-123")
        assert status_done["status"] == "completed"
        assert status_done["result"] == {"saved": 5}

