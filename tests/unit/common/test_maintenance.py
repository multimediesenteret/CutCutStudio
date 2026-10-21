"""SO-7: nightly upkeep – old rows purged, a consistent copy of the database, 7 kept, never
during a session, and catching up when the PC was off at night."""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cutcut.app import maintenance as mt
from cutcut.app.maintenance import Maintenance
from cutcut.common.store import Store

T0 = datetime(2026, 10, 21, 3, 30, tzinfo=UTC)


class Rig:
    def __init__(self, tmp: Path) -> None:
        self.t = T0
        self.session = False
        self.store = Store(tmp / "cutcut.db")
        self.m = Maintenance(self.store, tmp / "backup", lambda: self.t, lambda: self.session)


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def test_the_copy_is_a_working_database(rig: Rig) -> None:
    rig.store.put_kv("devices", {"atem": "10.0.0.1"}, T0)
    rig.store.flush()
    out = rig.m.run_once()
    assert out.name == "cutcut-2026-10-21-0330.db"
    con = sqlite3.connect(out)
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("SELECT value FROM kv WHERE key='devices'").fetchone()[0] == (
            '{"atem": "10.0.0.1"}'
        )
    finally:
        con.close()


def test_old_rows_are_purged(rig: Rig) -> None:
    rig.store.audit(T0 - timedelta(days=400), "admin", "magnus", "test")
    rig.store.audit(T0 - timedelta(days=2), "admin", "magnus", "test")
    rig.store.flush()
    rig.m.run_once()
    assert rig.store.count("audit") == 1


def test_seven_copies_are_kept(rig: Rig) -> None:
    for day in range(10):
        rig.t = T0 + timedelta(days=day)
        rig.m.run_once()
    names = [p.name for p in rig.m.backups()]
    assert len(names) == 7
    assert names[0] == "cutcut-2026-10-24-0330.db"
    assert not list(rig.m.backup_dir.glob("*.tmp"))


def test_once_a_night_and_never_during_a_session(rig: Rig) -> None:
    rig.t = T0.replace(hour=22)
    assert rig.m.due()  # no copy at all yet: at the next quiet moment
    rig.m.run_once()
    assert not rig.m.due()  # done today
    rig.t = T0 + timedelta(days=1)  # 03:30 the next night
    rig.session = True
    assert not rig.m.due()  # someone is recording at 03:30: wait
    rig.session = False
    assert rig.m.due()
    rig.m.run_once()
    rig.t += timedelta(hours=8)  # 11:30, copy from tonight: wait for the next night
    assert not rig.m.due()


def test_catches_up_when_the_pc_was_off_at_night(rig: Rig) -> None:
    rig.m.run_once()
    rig.t = T0 + timedelta(days=2, hours=8)  # off two nights, on at 11:30
    assert rig.m.due()


def test_a_failure_waits_for_tomorrow(rig: Rig, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Path:
        raise OSError("disken er full")

    monkeypatch.setattr(rig.m, "backup", boom)
    monkeypatch.setattr(mt, "CHECK_S", 0.0)

    async def go() -> None:
        task = asyncio.create_task(rig.m.run())
        await asyncio.sleep(0.05)
        task.cancel()

    asyncio.run(go())
    assert rig.m.last_error == "disken er full"
    assert not rig.m.due()  # not every minute: tomorrow
