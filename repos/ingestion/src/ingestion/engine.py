import logging
from datetime import datetime, timezone
from uuid import uuid4

from .cleaning import required_text
from .contracts import Cleaner, Source, Store
from .models import IngestedRecord, RunResult

logger = logging.getLogger(__name__)


class IngestionEngine:
    def __init__(self, cleaner: Cleaner, store: Store):
        self.cleaner = cleaner
        self.store = store

    def run(self, source: Source) -> RunResult:
        name = required_text(source.name, "source name")
        run_id = str(uuid4())
        started_at = datetime.now(timezone.utc).isoformat()
        logger.info("Starting run %s source=%s", run_id, name)
        try:
            batch = []
            seen = set()
            for raw in source.fetch():
                clean = self.cleaner.clean(raw)
                key = (clean.entity, clean.external_id)
                if key in seen:
                    raise ValueError(f"Duplicate record in batch: {key}")
                seen.add(key)
                batch.append(IngestedRecord(raw, clean))
            written = self.store.write_batch(name, run_id, started_at, batch)
        except Exception:
            logger.exception("Failed run %s source=%s", run_id, name)
            raise
        logger.info("Completed run %s retrieved=%d written=%d", run_id, len(batch), written)
        return RunResult(run_id, name, len(batch), written)
