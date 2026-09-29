"""Source-independent envelopes; basketball-specific schemas can be added later."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RawRecord:
    entity: str
    external_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class CleanRecord:
    entity: str
    external_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class IngestedRecord:
    raw: RawRecord
    clean: CleanRecord


@dataclass(frozen=True)
class RunResult:
    run_id: str
    source: str
    retrieved: int
    written: int
