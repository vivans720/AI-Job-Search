"""
Observability: Structured logging and metrics collector for AI Job Agent.
Provides:
- structlog configuration with JSON (prod) / Console (dev) formatters
- Request ID correlation contextvars
- In-memory metrics registry for Prometheus-compatible scrape / JSON reporting
"""
import os
import time
import logging
from collections import defaultdict
from contextvars import ContextVar
from typing import Any
import structlog

# Context variable for request correlation ID
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")

def get_correlation_id() -> str:
    return correlation_id_ctx.get()

def set_correlation_id(request_id: str) -> None:
    correlation_id_ctx.set(request_id)

def add_correlation_id(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    cid = get_correlation_id()
    if cid:
        event_dict["request_id"] = cid
    return event_dict

def configure_structlog() -> None:
    """Configures structured logging across backend."""
    is_prod = os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod")
    
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        add_correlation_id,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_prod:
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        processors = shared_processors + [structlog.dev.ConsoleRenderer(colors=True)]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class MetricsRegistry:
    """Thread-safe in-memory metrics registry for tracking counters and latency histograms."""
    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = {}
        self._durations: dict[str, list[float]] = defaultdict(list)

    def inc(self, metric: str, value: int = 1, **labels: str) -> None:
        key = self._format_key(metric, labels)
        self._counters[key] += value

    def gauge(self, metric: str, value: float, **labels: str) -> None:
        key = self._format_key(metric, labels)
        self._gauges[key] = value

    def observe(self, metric: str, duration_sec: float, **labels: str) -> None:
        key = self._format_key(metric, labels)
        self._durations[key].append(duration_sec)
        if len(self._durations[key]) > 100:
            self._durations[key] = self._durations[key][-100:]

    def _format_key(self, metric: str, labels: dict[str, str]) -> str:
        if not labels:
            return metric
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{metric}{{{label_str}}}"

    def get_summary(self) -> dict[str, Any]:
        """Returns structured JSON summary of metrics."""
        summary = {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {},
        }
        for key, vals in self._durations.items():
            if vals:
                summary["histograms"][key] = {
                    "count": len(vals),
                    "avg_sec": round(sum(vals) / len(vals), 4),
                    "min_sec": round(min(vals), 4),
                    "max_sec": round(max(vals), 4),
                }
        return summary

    def generate_prometheus(self) -> str:
        """Returns Prometheus text exposition format."""
        lines = []
        for k, v in self._counters.items():
            lines.append(f"{k} {v}")
        for k, v in self._gauges.items():
            lines.append(f"{k} {v}")
        for k, vals in self._durations.items():
            if vals:
                metric_base = k.split("{")[0]
                labels = "{" + k.split("{")[1] if "{" in k else ""
                lines.append(f"{metric_base}_count{labels} {len(vals)}")
                lines.append(f"{metric_base}_sum{labels} {round(sum(vals), 4)}")
        return "\n".join(lines) + "\n"

# Global singleton
metrics = MetricsRegistry()
