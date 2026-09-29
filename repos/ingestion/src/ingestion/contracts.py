from collections.abc import Iterable, Sequence
from typing import Protocol

from .models import CleanRecord, IngestedRecord, RawRecord


class Source(Protocol):
    """API or scraper adapter. Own authentication, pagination, timeouts and retries.

    name must be stable and unique across datasets. Emit stable upstream IDs,
    including season/game scope where needed. Raise if retrieval is incomplete.
    """
    name: str

    def fetch(self) -> Iterable[RawRecord]: ...


class Cleaner(Protocol):
    """Map a source record to a validated record; raise on invalid input."""
    def clean(self, record: RawRecord) -> CleanRecord: ...


class Store(Protocol):
    """Persist a complete batch and its run metadata atomically."""
    def write_batch(
        self, source: str, run_id: str, started_at: str,
        records: Sequence[IngestedRecord],
    ) -> int: ...
