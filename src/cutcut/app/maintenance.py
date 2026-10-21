"""Nightly upkeep in ``core`` (SO-7, plan supervisor-ops 2): the studio runs for months without
anyone tidying up, so CutCut does it itself.

* Old rows go from the database by the retention rules (``Store.purge``; sessions after Q10).
* A copy of ``cutcut.db`` is made in ``data\\backup\\`` with SQLite's online backup, so the
  copy is consistent even while CutCut writes. The newest 7 are kept.
* Logs rotate by themselves (30 days, ``common/logging.py``).

It runs once a night, between 03:00 and 05:00, and never while a session is running; if the
newest copy is more than 26 hours old (the PC was off at night), it runs at the next quiet
moment instead. Nothing here touches recordings: they live on the Pearl.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final

from cutcut.common.store import Store

log = logging.getLogger(__name__)

KEEP: Final = 7
NIGHT: Final = (3, 5)  # local hours: from 03:00 up to 05:00
STALE: Final = timedelta(hours=26)
CHECK_S: Final = 60.0
PREFIX: Final = "cutcut-"


@dataclass
class Maintenance:
    store: Store
    backup_dir: Path
    now: Callable[[], datetime]  # local wall-clock time
    busy: Callable[[], bool]  # a session is running: wait
    keep: int = KEEP
    last: datetime | None = None
    last_error: str | None = None
    _ran_on: str | None = field(default=None, init=False)

    def backups(self) -> list[Path]:
        """Copies, oldest first."""
        if not self.backup_dir.is_dir():
            return []
        return sorted(self.backup_dir.glob(f"{PREFIX}*.db"))

    def newest(self) -> datetime | None:
        files = self.backups()
        if not files:
            return None
        stamp = files[-1].stem.removeprefix(PREFIX)
        try:
            return datetime.strptime(stamp, "%Y-%m-%d-%H%M").replace(tzinfo=self.now().tzinfo)
        except ValueError:
            return None

    def due(self) -> bool:
        if self.busy():
            return False
        now = self.now()
        if self._ran_on == now.date().isoformat():
            return False  # once a day, also after a failure
        newest = self.newest()
        if newest is None or now - newest > STALE:
            return True
        return NIGHT[0] <= now.hour < NIGHT[1]

    def backup(self) -> Path:
        """A consistent copy of the database, then the oldest copies over ``keep`` go."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        now = self.now()
        out = self.backup_dir / f"{PREFIX}{now:%Y-%m-%d-%H%M}.db"
        tmp = out.with_suffix(".tmp")
        src = sqlite3.connect(self.store.path)
        try:
            dst = sqlite3.connect(tmp)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        tmp.replace(out)
        for old in self.backups()[: -self.keep]:
            old.unlink(missing_ok=True)
        return out

    def run_once(self) -> Path:
        now = self.now()
        self.store.purge(now)
        self.store.flush()  # the copy should not have what was just purged
        out = self.backup()
        self.last, self._ran_on, self.last_error = now, now.date().isoformat(), None
        log.info("Nattlig vedlikehold: gamle rader ryddet, kopi i %s", out)
        return out

    async def run(self) -> None:
        """Check once a minute until cancelled."""
        while True:
            try:
                if self.due():
                    await asyncio.to_thread(self.run_once)
            except Exception as e:  # a full disk must not take core down
                self.last_error = str(e)
                self._ran_on = self.now().date().isoformat()  # try again tomorrow
                log.exception("Nattlig vedlikehold feilet")
            await asyncio.sleep(CHECK_S)
