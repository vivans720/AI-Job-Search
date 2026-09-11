from enum import Enum
from typing import Any, Optional


class ErrorCategory(str, Enum):
    TRANSIENT_NETWORK = "transient_network"
    RATE_LIMIT_BLOCK = "rate_limit_block"
    PARSE_EXTRACTION = "parse_extraction"
    SOURCE_CONFIG = "source_config"
    FATAL = "fatal"


class SourceIngestionError(Exception):
    """Base exception for source crawling & ingestion errors."""

    def __init__(
        self,
        message: str,
        source: str,
        category: ErrorCategory = ErrorCategory.FATAL,
        status_code: Optional[int] = None,
        retryable: bool = False,
        raw_error: Optional[Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.source = source
        self.category = category
        self.status_code = status_code
        self.retryable = retryable
        self.raw_error = raw_error

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "category": self.category.value,
            "message": self.message,
            "status_code": self.status_code,
            "retryable": self.retryable,
        }


class TransientNetworkError(SourceIngestionError):
    """Temporary network failure (DNS, connection reset, HTTP 5xx, timeout)."""

    def __init__(self, message: str, source: str, status_code: Optional[int] = None, raw_error: Optional[Any] = None):
        super().__init__(
            message=message,
            source=source,
            category=ErrorCategory.TRANSIENT_NETWORK,
            status_code=status_code,
            retryable=True,
            raw_error=raw_error,
        )


class RateLimitBlockError(SourceIngestionError):
    """Perimeter defense or rate limit encountered (HTTP 429, 999, Cloudflare challenge, Captcha)."""

    def __init__(self, message: str, source: str, status_code: Optional[int] = None, raw_error: Optional[Any] = None):
        super().__init__(
            message=message,
            source=source,
            category=ErrorCategory.RATE_LIMIT_BLOCK,
            status_code=status_code,
            retryable=False,
            raw_error=raw_error,
        )


class ParseExtractionError(SourceIngestionError):
    """Failure parsing expected HTML elements or JSON structures."""

    def __init__(self, message: str, source: str, raw_error: Optional[Any] = None):
        super().__init__(
            message=message,
            source=source,
            category=ErrorCategory.PARSE_EXTRACTION,
            status_code=None,
            retryable=False,
            raw_error=raw_error,
        )


def classify_error(exc: Exception, source: str, status_code: Optional[int] = None) -> SourceIngestionError:
    """Classifies generic exceptions or HTTP status codes into standardized SourceIngestionError."""
    if isinstance(exc, SourceIngestionError):
        return exc

    err_str = str(exc).lower()

    if status_code in (429, 999, 403) or any(
        kw in err_str for kw in ("rate limit", "too many requests", "challenge", "perimeter", "captcha", "blocked", "status 999", "status 429")
    ):
        return RateLimitBlockError(
            message=f"Source {source} rate limited or blocked: {str(exc)}",
            source=source,
            status_code=status_code,
            raw_error=exc,
        )

    if (status_code and status_code >= 500) or any(
        kw in err_str for kw in ("timeout", "timed out", "connection reset", "connecterror", "connection refused", "remotedisconnected", "ssl")
    ):
        return TransientNetworkError(
            message=f"Source {source} transient network error: {str(exc)}",
            source=source,
            status_code=status_code,
            raw_error=exc,
        )

    exc_type_name = type(exc).__name__.lower()
    if isinstance(exc, (KeyError, AttributeError, LookupError)) or any(kw in err_str or kw in exc_type_name for kw in ("jsondecodeerror", "attributeerror", "keyerror", "selector", "parse")):
        return ParseExtractionError(
            message=f"Source {source} parsing error: {str(exc)}",
            source=source,
            raw_error=exc,
        )

    return SourceIngestionError(
        message=f"Source {source} error: {str(exc)}",
        source=source,
        category=ErrorCategory.FATAL,
        status_code=status_code,
        retryable=False,
        raw_error=exc,
    )
