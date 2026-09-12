import asyncio
import functools
import inspect
import random
import time
from typing import Any, Callable, TypeVar
import structlog

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN and request is rejected."""
    pass


class CircuitBreaker:
    """
    Circuit breaker state machine: CLOSED -> OPEN -> HALF_OPEN.
    Protects downstream systems (LLM, scrapers, APIs) from repeated failures.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout_sec: float = 30.0,
        half_open_success_threshold: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.half_open_success_threshold = half_open_success_threshold

        self.state = "CLOSED"  # "CLOSED", "OPEN", "HALF_OPEN"
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0

    def record_success(self) -> None:
        if self.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= self.half_open_success_threshold:
                self.state = "CLOSED"
                self.failure_count = 0
                self.success_count = 0
                logger.info("circuit_breaker_closed", breaker=self.name)
        elif self.state == "CLOSED":
            self.failure_count = 0

    def record_failure(self, error: Exception | None = None) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        logger.warning(
            "circuit_breaker_failure_recorded",
            breaker=self.name,
            failures=self.failure_count,
            state=self.state,
            error=str(error) if error else None,
        )
        if self.state in ("CLOSED", "HALF_OPEN") and self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(
                "circuit_breaker_tripped_open",
                breaker=self.name,
                failures=self.failure_count,
                recovery_timeout=self.recovery_timeout_sec,
            )

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.recovery_timeout_sec:
                self.state = "HALF_OPEN"
                self.success_count = 0
                logger.info("circuit_breaker_half_open_probe", breaker=self.name)
                return True
            return False
        if self.state == "HALF_OPEN":
            return True
        return False

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if not self.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN. Requests blocked to prevent cascading failure."
            )
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise


_BREAKERS: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 3,
    recovery_timeout_sec: float = 30.0,
    half_open_success_threshold: int = 2,
) -> CircuitBreaker:
    if name not in _BREAKERS:
        _BREAKERS[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout_sec=recovery_timeout_sec,
            half_open_success_threshold=half_open_success_threshold,
        )
    return _BREAKERS[name]


def retry_with_backoff(
    retries: int = 3,
    base_delay_sec: float = 0.5,
    max_delay_sec: float = 5.0,
    jitter: bool = True,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """
    Exponential backoff retry decorator with optional random jitter.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_err = None
            delay = base_delay_sec
            for attempt in range(1, retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_exceptions as e:
                    last_err = e
                    if attempt == retries:
                        logger.warning(
                            "retry_exhausted",
                            func=func.__name__,
                            attempt=attempt,
                            max_retries=retries,
                            error=str(e),
                        )
                        raise
                    sleep_time = delay
                    if jitter:
                        sleep_time += random.uniform(0, delay * 0.5)
                    sleep_time = min(sleep_time, max_delay_sec)
                    logger.info(
                        "retry_attempt_failed_backing_off",
                        func=func.__name__,
                        attempt=attempt,
                        next_delay=round(sleep_time, 2),
                        error=str(e),
                    )
                    await asyncio.sleep(sleep_time)
                    delay *= 2
            if last_err:
                raise last_err

        return async_wrapper
    return decorator
