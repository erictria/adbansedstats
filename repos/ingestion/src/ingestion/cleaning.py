import math
from typing import Any

from .models import CleanRecord, RawRecord


def required_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def normalize(value: Any) -> Any:
    """Trim text recursively without guessing numeric or date semantics."""
    if isinstance(value, str):
        return value.strip()
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite numbers are not valid data")
        return value
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key = required_text(key, "payload key")
            if key in result:
                raise ValueError(f"Duplicate payload key after cleaning: {key}")
            result[key] = normalize(item)
        return result
    raise ValueError(f"Unsupported payload type: {type(value).__name__}")


class DefaultCleaner:
    def clean(self, record: RawRecord) -> CleanRecord:
        if not isinstance(record.payload, dict):
            raise ValueError("payload must be an object")
        return CleanRecord(
            entity=required_text(record.entity, "entity"),
            external_id=required_text(record.external_id, "external_id"),
            payload=normalize(record.payload),
        )
