"""HS-1: the health engine – intervals, broken checks, hysteresis, one issue per problem."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cutcut.health import CheckResult, FuncCheck, HealthEngine, HealthEvent, Status
from cutcut.health.checks import audio_stream
from tests.unit.api.test_api import Rig


class Clock:
    def __init__(self) -> None:
        self.t = 0.0

    def mono(self) -> float:
        return self.t

    def now(self) -> datetime:
        return datetime(2026, 10, 21, 8, 0, tzinfo=UTC)


class Device:
    """A check whose answer the test sets."""

    def __init__(self, cid: str = "H-TEST-1", interval: float = 1.0) -> None:
        self.status: Status = "green"
        self.calls = 0
        self.check = FuncCheck(cid, interval, self.run)
        self.cid = cid

    def run(self) -> CheckResult:
        self.calls += 1
        return CheckResult(
            id=self.cid,
            status=self.status,
            value=self.status,
            message=f"enheten er {self.status}",
            ts=datetime(2026, 10, 21, tzinfo=UTC),
        )


@pytest.fixture
def clock() -> Clock:
    return Clock()


def engine(clock: Clock, *checks: FuncCheck) -> tuple[HealthEngine, list[HealthEvent]]:
    events: list[HealthEvent] = []
    return HealthEngine(checks, clock.mono, clock.now, on_event=events.append), events


def run(eng: HealthEngine, clock: Clock, seconds: float, step: float = 0.25) -> None:
    for _ in range(int(seconds / step)):
        asyncio.run(eng.step())
        clock.t += step


def test_each_check_runs_on_its_own_interval(clock: Clock) -> None:
    fast, slow = Device("H-A", 1.0), Device("H-B", 5.0)
    eng, _ = engine(clock, fast.check, slow.check)
    run(eng, clock, 10)
    assert fast.calls == 10
    assert slow.calls == 2


def test_a_flapping_device_gives_one_issue_resolved_after_30_s_green(clock: Clock) -> None:
    dev = Device()
    eng, events = engine(clock, dev.check)
    run(eng, clock, 2)
    assert events == []
    for _ in range(5):  # red, green, red, green … for 20 s
        dev.status = "red"
        run(eng, clock, 2)
        dev.status = "green"
        run(eng, clock, 2)
    assert [e.kind for e in events] == ["opened"]
    assert eng.overall() == "red"  # still open: not 30 s green yet
    green_for = 2.0
    while len(events) == 1 and green_for < 60:
        run(eng, clock, 0.25)
        green_for += 0.25
    assert [e.kind for e in events] == ["opened", "resolved"]
    assert 29.0 <= green_for <= 32.0
    assert events[1].duration_s >= 45  # from the first red to resolved
    assert eng.overall() == "green"


def test_getting_worse_or_better_while_open_is_one_event_each(clock: Clock) -> None:
    dev = Device()
    eng, events = engine(clock, dev.check)
    for status in ("yellow", "yellow", "red", "red", "yellow"):
        dev.status = status
        run(eng, clock, 1)
    assert [(e.kind, e.result.status) for e in events] == [
        ("opened", "yellow"),
        ("changed", "red"),
        ("changed", "yellow"),
    ]
    assert eng.results()[0].since is not None  # the screen shows how long it has lasted


def test_a_check_that_throws_is_yellow_never_a_crash(clock: Clock) -> None:
    def boom() -> CheckResult:
        raise ConnectionError("nei")

    eng, events = engine(clock, FuncCheck("H-X", 1.0, boom))
    run(eng, clock, 1)
    (r,) = eng.results()
    assert r.status == "yellow"
    assert r.value == "sjekken virker ikke"
    assert "ConnectionError" in r.message
    assert events[0].kind == "opened"


def test_a_check_that_hangs_times_out(clock: Clock) -> None:
    async def hang() -> CheckResult:
        await asyncio.sleep(10)
        raise AssertionError

    eng, _ = engine(clock, FuncCheck("H-SLOW", 1.0, hang, timeout_s=0.05))
    run(eng, clock, 0.25)
    assert "svarte ikke innen 0.05 s" in eng.results()[0].message


def test_a_check_must_answer_with_its_own_id(clock: Clock) -> None:
    other = Device("H-OTHER")
    eng, _ = engine(clock, FuncCheck("H-MINE", 1.0, other.run))
    run(eng, clock, 0.25)
    assert eng.results()[0].status == "yellow"


def test_ids_are_unique(clock: Clock) -> None:
    with pytest.raises(ValueError, match="to ganger"):
        engine(clock, Device().check, Device().check)


def test_run_all_runs_everything_now(clock: Clock) -> None:
    a, b = Device("H-A", 60), Device("H-B", 600)
    eng, _ = engine(clock, a.check, b.check)
    run(eng, clock, 1)
    got = asyncio.run(eng.run_all())
    assert (a.calls, b.calls) == (2, 2)
    assert {r.id for r in got} == {"H-A", "H-B"}


@pytest.mark.parametrize(
    ("age", "status"), [(None, "red"), (40, "green"), (2_000, "green"), (2_001, "red")]
)
def test_H_AUD_1(clock: Clock, age: int | None, status: str) -> None:
    r = asyncio.run(audio_stream(lambda: age, clock.now).run())
    assert r.id == "H-AUD-1"
    assert r.status == status
    assert not r.for_user  # the user hears it from S4, not twice


# -- in the studio ------------------------------------------------------------------------------


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def health_step(rig: Rig, seconds: float) -> None:
    """Studio time and health in step, as in core (ticks plus the health loop)."""
    for _ in range(int(seconds * 4)):
        rig.run(250)
        asyncio.run(rig.sim.studio.health.step())


def test_lost_audio_opens_an_alert_that_goes_away_by_itself(rig: Rig) -> None:
    c = rig.client
    health_step(rig, 2)
    checks = {x["id"]: x["status"] for x in c.get("/api/health/checks").json()}
    assert checks["H-AUD-1"] == "green"
    assert c.get("/api/health").json()["health"]["status"] == "green"

    c.post("/api/sim/fault", json={"kind": "audio_lost", "on": True})
    health_step(rig, 4)
    body = c.get("/api/health").json()
    assert body["status"] == "error"
    assert {x["id"]: x["status"] for x in body["health"]["checks"]}["H-AUD-1"] == "red"
    assert [a["code"] for a in rig.state()["alerts"]].count("H-AUD-1") == 1

    c.post("/api/sim/fault", json={"kind": "audio_lost", "on": False})
    health_step(rig, 10)
    assert "H-AUD-1" in [a["code"] for a in rig.state()["alerts"]]  # not yet: hysteresis
    health_step(rig, 25)
    assert "H-AUD-1" not in [a["code"] for a in rig.state()["alerts"]]
    assert rig.state()["health"]["status"] == "green"
