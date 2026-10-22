"""Feilsøkingsmodus: on for a while from the technician window, records what reaches the engine
(bus, decisions, intents, Companion presses with their time), and turns itself off."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest

from cutcut.app.debugrec import DebugRecorder, read
from cutcut.common.clock import FakeClock
from tests.unit.api.test_api import Rig


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    r.sim.studio.debug.folder = tmp_path / "debug"
    r.sim.studio.debug._use_thread = False  # write when it stops, no thread in tests
    yield r
    r.store.close()
    logging.getLogger().setLevel(logging.INFO)


def test_on_records_the_session_and_off_writes_it(rig: Rig) -> None:
    c = rig.client
    r = c.put("/api/debug", json={"hours": 1})
    assert r.status_code == 200
    assert r.json()["on"] is True
    assert rig.state()["studio"]["debug_until"] is not None
    assert logging.getLogger().level == logging.DEBUG
    c.post("/api/sim/card", json={"card": "04A1B2C3"})
    c.put("/api/session/show", json={"guests": 1, "video": True})
    c.post("/api/recording", json={"action": "start"})
    c.post("/api/sim/talk", json={"participant": "P2", "on": True})
    rig.run(8000)
    rig.sim.studio.runtime.feed_bus("audio.status", {"backend": "asio"})
    rig.sim.studio.runtime.feed_bus("vision.thumbs", {"thumbs": {"C1": "x" * 1000}})
    assert c.put("/api/debug", json={"hours": 0}).json()["on"] is False
    records = read(rig.sim.studio.debug.files())
    kinds = {r["kind"] for r in records}
    assert {"bus", "decision", "intent"} <= kinds
    topics = {r.get("topic") for r in records if r["kind"] == "bus"}
    assert "audio.status" in topics
    assert "vision.thumbs" not in topics  # pictures are not recorded
    assert all("t" in r and "mono" in r for r in records)
    assert logging.getLogger().level == logging.INFO


def test_only_admin_turns_it_on(tmp_path: Path) -> None:
    r = Rig(tmp_path, dev_admin=False)
    try:
        assert r.client.put("/api/debug", json={"hours": 1}).status_code in (401, 403)
    finally:
        r.store.close()


def test_hours_are_limited(rig: Rig) -> None:
    assert rig.client.put("/api/debug", json={"hours": 100}).status_code == 422


def test_it_turns_itself_off_and_survives_a_restart(tmp_path: Path) -> None:
    clock = FakeClock()
    rec = DebugRecorder(tmp_path, clock.now, clock.mono_ms, thread=False)
    rec.start(clock.now() + timedelta(hours=1))
    rec.bus("atem.state", {"program_input": 1})
    clock.advance(30 * 60_000)
    assert not rec.expire()
    clock.advance(31 * 60_000)
    assert rec.expire()
    assert not rec.active
    assert [r["topic"] for r in read(rec.files())] == ["atem.state"]


def test_still_on_after_a_restart(rig: Rig) -> None:
    rig.client.put("/api/debug", json={"hours": 8})
    from cutcut.app.studio import Studio, StudioDeps

    again = Studio(StudioDeps(**{**rig.sim.studio.deps.__dict__}))
    try:
        assert again.debug.active
    finally:
        again.debug.stop()
