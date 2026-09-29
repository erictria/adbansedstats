import json
from collections.abc import Iterable
from pathlib import Path

from ..models import RawRecord


class JsonFileSource:
    """Local fixture adapter for exercising the pipeline without network access."""
    def __init__(self, path: Path, name: str):
        self.path = path
        self.name = name

    def fetch(self) -> Iterable[RawRecord]:
        records = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("Input must be a JSON array of records")
        for index, item in enumerate(records):
            if not isinstance(item, dict) or not {"entity", "external_id", "payload"} <= item.keys():
                raise ValueError(f"Record {index} needs entity, external_id, and payload")
            yield RawRecord(item["entity"], item["external_id"], item["payload"])
