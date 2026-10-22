"""Kill tests for the supervisor (SO-1): real child processes, a clock we move by hand."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from cutcut.supervisor import supervisor as sv
from cutcut.supervisor.main import effective_atem_ip
from cutcut.supervisor.supervisor import ProcessSpec, Supervisor

ROOT = Path(__file__).resolve().parents[3]
SLEEPER = [sys.executable, "-c", "import time; time.sleep(60)"]
CRASHER = [sys.executable, "-c", "import sys; sys.exit(3)"]


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def wait(cond: Callable[[], bool], timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def make(clock: Clock) -> Iterator[Callable[..., Supervisor]]:
    made: list[Supervisor] = []

    def build(*specs: ProcessSpec, **kw: object) -> Supervisor:
        s = Supervisor(specs, clock=clock, **kw)  # type: ignore[arg-type]
        made.append(s)
        return s

    yield build
    for s in made:
        s.stop_all()


def test_a_killed_process_is_started_again(make: Callable[..., Supervisor], clock: Clock) -> None:
    sup = make(ProcessSpec("core", SLEEPER))
    sup.step()
    st = sup.states["core"]
    assert st.running
    assert st.proc is not None
    first = st.proc.pid

    st.proc.kill()  # like Task Manager's «End task»
    assert wait(lambda: st.proc is not None and st.proc.poll() is not None)
    sup.step()
    assert not st.running
    assert sup.status()[0]["last_reason"].startswith("avsluttet med kode")

    clock.t += 0.5
    sup.step()
    assert st.proc is None  # still within the 1 s pause

    clock.t += 0.6
    sup.step()
    assert st.running
    assert st.proc is not None
    assert st.proc.pid != first
    assert sup.status()[0]["restarts_10min"] == 1


def test_pause_grows_1_2_5_10_30_and_resets_after_stable_running(
    make: Callable[..., Supervisor], clock: Clock
) -> None:
    sup = make(ProcessSpec("audio-capture", CRASHER))
    st = sup.states["audio-capture"]
    pauses = []
    for _ in range(6):
        sup.step()  # start
        assert st.proc is not None
        assert wait(lambda: st.proc is not None and st.proc.poll() is not None)
        sup.step()  # notices the exit and schedules
        pauses.append(st.next_start - clock.t)
        clock.t = st.next_start
    assert pauses == [1.0, 2.0, 5.0, 10.0, 30.0, 30.0]

    # A process that then runs well for a minute gets the short pause again.
    sup.states["audio-capture"] = st = sv.ProcessState(ProcessSpec("audio-capture", SLEEPER))
    st.attempt = 5
    sup.step()
    clock.t += sv.STABLE_S
    sup.step()
    assert st.attempt == 0


def test_a_hanging_process_is_killed_and_started_again(
    make: Callable[..., Supervisor], clock: Clock
) -> None:
    healthy = {"ok": True}
    sup = make(ProcessSpec("core", SLEEPER, health=lambda: healthy["ok"], health_every_s=2.0))
    st = sup.states["core"]
    sup.step()
    hung = st.proc
    assert hung is not None

    clock.t += 5.0
    sup.step()
    assert st.health_fails == 0

    healthy["ok"] = False  # alive, but answers nothing
    for _ in range(sv.HEALTH_FAILS):
        clock.t += 2.0
        sup.step()
    assert st.proc is None
    assert hung.poll() is not None  # really gone, not left behind
    assert st.last_reason == "svarte ikke (hang)"

    healthy["ok"] = True
    clock.t += 1.0
    sup.step()
    assert st.running


def test_a_health_check_that_raises_counts_as_failed(
    make: Callable[..., Supervisor], clock: Clock
) -> None:
    def boom() -> bool:
        raise RuntimeError("no")

    sup = make(ProcessSpec("core", SLEEPER, health=boom, health_every_s=1.0))
    sup.step()
    for _ in range(sv.HEALTH_FAILS):
        clock.t += 5.0
        sup.step()
    assert sup.states["core"].last_reason == "svarte ikke (hang)"


def test_more_than_five_restarts_in_ten_minutes_is_reported(
    make: Callable[..., Supervisor], clock: Clock
) -> None:
    flaps: list[tuple[str, int]] = []
    sup = make(ProcessSpec("atem-bridge", CRASHER), on_flap=lambda n, c: flaps.append((n, c)))
    st = sup.states["atem-bridge"]
    for _ in range(6):
        sup.step()
        assert wait(lambda: st.proc is not None and st.proc.poll() is not None)
        sup.step()
        clock.t = st.next_start
    assert flaps == [("atem-bridge", 6)]

    clock.t += sv.FLAP_WINDOW_S + 1  # an hour later the count has gone back down
    assert sup.status()[0]["restarts_10min"] == 0


def test_arguments_are_read_again_at_every_start(
    make: Callable[..., Supervisor], clock: Clock
) -> None:
    calls = {"n": 0}

    def args() -> list[str]:
        calls["n"] += 1
        return CRASHER

    sup = make(ProcessSpec("atem-bridge", args))
    st = sup.states["atem-bridge"]
    sup.step()
    assert wait(lambda: st.proc is not None and st.proc.poll() is not None)
    sup.step()
    clock.t = st.next_start
    sup.step()
    assert calls["n"] == 2


def test_a_missing_program_is_retried_not_fatal(
    make: Callable[..., Supervisor], clock: Clock
) -> None:
    sup = make(ProcessSpec("vision", ["/finnes/ikke/cutcut-vision"]))
    sup.step()
    st = sup.states["vision"]
    assert st.proc is None
    assert st.last_reason is not None
    assert st.last_reason.startswith("kunne ikke startes")
    assert st.next_start == clock.t + 1.0


def test_stop_all_stops_every_child(make: Callable[..., Supervisor]) -> None:
    sup = make(ProcessSpec("a", SLEEPER), ProcessSpec("b", SLEEPER))
    sup.step()
    procs = [st.proc for st in sup.states.values()]
    sup.stop_all()
    assert all(p is not None and p.poll() is not None for p in procs)


def test_atem_address_saved_on_screen_wins_over_devices_yaml(tmp_path: Path) -> None:
    site = ROOT / "site" / "multimediesenteret"
    data = tmp_path / "data"
    from_file = effective_atem_ip(site, data)  # no database yet: devices.yaml

    data.mkdir()
    conn = sqlite3.connect(data / "cutcut.db")
    conn.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute(
        "INSERT INTO kv VALUES (?, ?)", ("site.devices", json.dumps({"atem.ip": "10.20.30.40"}))
    )
    conn.commit()
    conn.close()
    assert effective_atem_ip(site, data) == "10.20.30.40"
    assert from_file != "10.20.30.40"


def test_children_die_when_the_supervisor_is_killed_hard(tmp_path: Path) -> None:
    """An orphaned core would hold port 8080 and make every new core fail (Job Object/PDEATHSIG)."""
    import subprocess

    beat = tmp_path / "beat.txt"
    child = (
        "import time, pathlib\n"
        f"p = pathlib.Path({str(beat)!r})\n"
        "while True:\n"
        "    p.write_text(str(time.monotonic()))\n"
        "    time.sleep(0.05)\n"
    )
    parent = (
        "import sys, time\n"
        "from cutcut.supervisor.supervisor import ProcessSpec, Supervisor\n"
        f"s = Supervisor([ProcessSpec('child', [sys.executable, '-c', {child!r}])])\n"
        "s.step()\n"
        "time.sleep(60)\n"
    )
    sup = subprocess.Popen([sys.executable, "-c", parent])  # noqa: S603
    try:
        assert wait(lambda: beat.exists() and beat.read_text() != "", 15)
        sup.kill()  # no chance to clean up
        sup.wait(5)

        def stopped() -> bool:
            before = beat.read_text()
            time.sleep(0.4)
            return beat.read_text() == before

        assert wait(stopped, 10)
    finally:
        sup.kill()


def test_stopping_a_process_also_stops_what_it_started(
    make: Callable[..., Supervisor], clock: Clock, tmp_path: Path
) -> None:
    """On Windows a venv's python.exe is a launcher with the real interpreter as its child;
    killing only the launcher would leave core holding its port."""
    import psutil

    pidfile = tmp_path / "child.pid"
    launcher = (
        "import subprocess, sys, time, pathlib\n"
        "c = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"pathlib.Path({str(pidfile)!r}).write_text(str(c.pid))\n"
        "time.sleep(60)\n"
    )
    healthy = {"ok": True}
    sup = make(
        ProcessSpec(
            "core",
            [sys.executable, "-c", launcher],
            health=lambda: healthy["ok"],
            health_every_s=1.0,
        )
    )
    sup.step()
    assert wait(lambda: pidfile.exists() and pidfile.read_text() != "")
    child = psutil.Process(int(pidfile.read_text()))
    healthy["ok"] = False
    for _ in range(sv.HEALTH_FAILS + 1):
        clock.t += 5.0
        sup.step()
    assert sup.states["core"].last_reason == "svarte ikke (hang)"
    assert wait(lambda: not child.is_running() or child.status() == psutil.STATUS_ZOMBIE)
