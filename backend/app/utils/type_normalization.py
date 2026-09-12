import math
from datetime import date, datetime
from typing import Any
import structlog

logger = structlog.get_logger(__name__)


def is_nan(val: Any) -> bool:
    """Returns True if val is float('nan') or numpy.nan."""
    return isinstance(val, float) and math.isnan(val)


def clean_text(val: Any, field_name: str | None = None) -> str | None:
    """
    Safely cleans a text value:
    - None -> None
    - float('nan') / NaN -> None
    - string -> stripped string (None if empty)
    - int / float -> logs debug notice and returns converted stripped string
    - other -> converted stripped string (None if empty)
    """
    if val is None:
        return None
    if is_nan(val):
        return None
    if isinstance(val, (int, float)):
        logger.debug("clean_text_converting_numeric", field=field_name, type=type(val).__name__)
        return clean_text(str(val), field_name)
    if isinstance(val, str):
        s = val.strip()
        return s if s else None
    # Fallback: convert to string
    s = str(val).strip()
    return s if s else None


def clean_record_value(val: Any) -> Any:
    """
    Recursively cleans values from external API dictionaries:
    - None -> None
    - NaN -> None
    - string -> stripped string
    - int, float -> preserved as numeric
    - bool -> preserved as boolean
    - date, datetime -> preserved as date/datetime
    - dict -> recursively cleaned
    - list/tuple -> recursively cleaned
    """
    if val is None:
        return None
    if is_nan(val):
        return None
    if isinstance(val, (datetime, date)):
        return val
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    if isinstance(val, (int, str, bool)):
        return val
    if isinstance(val, dict):
        return {str(k): clean_record_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [clean_record_value(x) for x in val]
    return val


def make_json_serializable(obj: Any) -> Any:
    """
    Recursively converts arbitrary Python structures into JSONB-compatible structures:
    - date -> 'YYYY-MM-DD'
    - datetime -> ISO-8601 string
    - NaN / Inf -> None
    - dict -> dict with string keys and serializable values
    - list/tuple/set -> list of serializable values
    - primitive JSON values (int, str, bool, None) -> unchanged
    """
    if obj is None:
        return None
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (int, str, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [make_json_serializable(x) for x in obj]
    if hasattr(obj, "model_dump"):
        return make_json_serializable(obj.model_dump())
    if hasattr(obj, "__dict__"):
        return make_json_serializable(obj.__dict__)
    return str(obj)
