"""HS-4: the whole catalogue at start-up and every morning at 07:00, shown as a dot."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC
from pathlib import Path

import pytest

from cutcut.app.studio import STARTUP_CHECK_MS
from tests.unit.api.test_api import Rig


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    r.sim.studio.local_tz = UTC  # the tests run in UTC; the studio uses the PC's own zone
    yield r
    r.store.close()


def loop(rig: Rig, seconds: float) -> None:
    for _ in range(int(seconds * 4)):
        rig.run(250)
        asyncio.run(rig.sim.studio.health.step())
        asyncio.run(rig.sim.studio._maybe_morning_check())


def test_start_up_check_after_the_devices_had_time_to_connect(rig: Rig) -> None:
    loop(rig, STARTUP_CHECK_MS / 1000 - 2)
    assert rig.state()["health"]["morning"] is None
    loop(rig, 3)
    m = rig.state()["health"]["morning"]
    assert m["reason"] == "oppstart"
    assert m["status"] == "green"
    assert m["failed"] == []


def test_every_morning_at_seven_local_time(rig: Rig) -> None:
    studio = rig.sim.studio
    loop(rig, 21)
    start = studio.deps.clock.now()  # the fake clock starts at noon: today's check is done
    assert start.hour >= 7
    asyncio.run(studio._maybe_morning_check())
    assert studio.morning is not None
    assert studio.morning.reason == "oppstart"

    to_6 = ((24 - start.hour + 6) * 3600 - start.minute * 60 - start.second) * 1000
    rig.clock.advance(to_6)  # 06:00 next day: not yet
    asyncio.run(studio._maybe_morning_check())
    assert studio.morning.reason == "oppstart"
    rig.clock.advance(3600 * 1000)  # 07:00
    asyncio.run(studio._maybe_morning_check())
    assert studio.morning.reason == "morgen"
    assert studio.morning.ts.endswith("07:00:00+00:00")
    first = studio.morning.ts
    rig.clock.advance(3 * 3600 * 1000)  # once a day
    asyncio.run(studio._maybe_morning_check())
    assert studio.morning.ts == first


def test_a_fault_gives_a_yellow_dot_and_names_the_checks(rig: Rig) -> None:
    loop(rig, 21)
    rig.client.post("/api/sim/fault", json={"kind": "companion_down", "on": True})
    rig.client.post("/api/sim/fault", json={"kind": "multiview_wrong", "on": True})
    loop(rig, 1)
    r = rig.client.post("/api/health/morning-check")
    assert r.status_code == 200
    body = r.json()
    assert body["reason"] == "manuell"
    assert body["status"] == "red"
    assert body["failed"] == ["H-COMP-1", "H-MV"]
    assert rig.state()["health"]["morning"]["failed"] == ["H-COMP-1", "H-MV"]


def test_only_staff_can_run_it(tmp_path: Path) -> None:
    r = Rig(tmp_path, dev_admin=False)
    try:
        assert r.client.post("/api/health/morning-check").status_code in (401, 403)
    finally:
        r.store.close()
