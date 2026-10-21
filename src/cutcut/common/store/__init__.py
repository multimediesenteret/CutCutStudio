"""Runtime data in SQLite (WAL) – sessions, decisions, audit log, config versions, alerts and
the engine's state snapshot (ADR-0006, docs/plans/common.md C-5).

Design for months without a technician:

* WAL + ``synchronous=NORMAL``: a killed process never leaves a corrupt database.
* All writes go through one writer thread with a bounded queue, so callers in the asyncio
  loop never block. If the queue is full or the disk fails, the write is dropped, counted
  and logged; the engine keeps running without storage (health turns yellow).
* ``purge()`` removes old rows according to retention, so the file does not grow forever.
* No card numbers are ever stored (I8); there is no column for them.
"""

from cutcut.common.store.store import Retention, Store, StoreStats

__all__ = ["Retention", "Store", "StoreStats"]
