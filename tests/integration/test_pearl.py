"""SE-2, SE-3, SIM-3: Pearl client and recorder against a fake Pearl over HTTP."""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from cutcut.common.models.session import RecordingStatus
from cutcut.devices.pearl.client import PearlError, PearlHttp
from cutcut.devices.pearl.recorder import OFFLINE_AFTER_S, PearlRecorder
from cutcut.sim.fake_pearl import FakePearlState, fake_pearl


@dataclass
class Clock:
    t: float = 100.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def pearl() -> Iterator[tuple[PearlHttp, FakePearlState]]:
    with fake_pearl() as (url, state):
        client = PearlHttp(url, "cutcut", "test-only")
        yield client, state
        client.close()


def polled(rec: PearlRecorder) -> RecordingStatus:
    rec.step()
    return rec.state


def wait_for(cond, timeout: float = 3.0) -> bool:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_client_reads_status_storage_and_firmware(pearl: tuple[PearlHttp, FakePearlState]) -> None:
    client, _ = pearl
    assert client.recorder_status("1").state is RecordingStatus.STOPPED
    assert client.firmware() == "4.24.1"
    [main] = client.storages()  # external drive not mounted, maintenance skipped
    assert main.id == "main"
    assert main.free_share == pytest.approx(0.7)


def test_client_start_and_stop(pearl: tuple[PearlHttp, FakePearlState]) -> None:
    client, state = pearl
    client.start("1")
    assert client.recorder_status("1").state is RecordingStatus.STARTING
    assert wait_for(lambda: client.recorder_status("1").state is RecordingStatus.STARTED)
    client.stop("1")
    assert client.recorder_status("1").state is RecordingStatus.STOPPED
    assert state.commands == [("1", "start"), ("1", "stop")]


def test_wrong_password_is_a_clear_error() -> None:
    with fake_pearl() as (url, _):
        client = PearlHttp(url, "cutcut", "feil")
        with pytest.raises(PearlError, match="innloggingen"):
            client.recorder_status("1")
        client.close()


def test_recorder_start_is_idempotent_and_confirmed(
    pearl: tuple[PearlHttp, FakePearlState],
) -> None:
    client, state = pearl
    rec = PearlRecorder(client, start_thread=False)
    rec.step()
    assert rec.state is RecordingStatus.STOPPED
    assert rec.start(0)
    assert rec.start(0)  # twice is the same as once
    assert rec.state is RecordingStatus.STARTING
    rec.step()
    assert state.commands == [("1", "start")]
    assert wait_for(lambda: polled(rec) is RecordingStatus.STARTED)
    assert rec.start(0)
    rec.step()
    assert state.commands == [("1", "start")]  # no second start command
    assert rec.stop(0)
    rec.step()
    assert rec.state is RecordingStatus.STOPPED
    assert rec.stop(0)
    rec.step()
    assert state.commands == [("1", "start"), ("1", "stop")]
    assert rec.status().firmware == "4.24.1"


def test_slow_start_stays_starting_not_stopped(pearl: tuple[PearlHttp, FakePearlState]) -> None:
    """A poll before the Pearl has started must not look like «stopped by itself»."""
    client, state = pearl
    rec = PearlRecorder(client, start_thread=False)
    rec.step()
    state.start_delay_s = 0.5
    rec.start(0)
    rec.step()
    with state.lock:
        state.recorders["1"] = "stopped"  # Pearl has not picked it up yet
    rec.step()
    assert rec.state is RecordingStatus.STARTING


def test_recording_that_stops_by_itself_is_reported_I7(
    pearl: tuple[PearlHttp, FakePearlState],
) -> None:
    client, state = pearl
    rec = PearlRecorder(client, start_thread=False)
    rec.start(0)
    rec.step()
    assert wait_for(lambda: polled(rec) is RecordingStatus.STARTED)
    state.stop_by_itself(error=True)
    rec._next_status = 0
    rec.step()
    assert rec.state is RecordingStatus.ERROR
    assert rec.last_error == "No space left on device"
    assert ("1", "stop") not in state.commands  # CutCut never stops a recording itself


def test_offline_pearl_refuses_start_at_once() -> None:
    clock = Clock()
    with fake_pearl(FakePearlState(fail=True)) as (url, _):
        client = PearlHttp(url, "cutcut", "test-only", timeout_s=0.3)
        rec = PearlRecorder(client, clock=clock, start_thread=False)
        rec.step()
        assert rec.last_error is not None
        clock.t += OFFLINE_AFTER_S + 1
        assert not rec.status().online
        assert rec.start(0) is False
        client.close()


def test_worker_thread_keeps_state_current(pearl: tuple[PearlHttp, FakePearlState]) -> None:
    client, _ = pearl
    rec = PearlRecorder(client)
    try:
        assert wait_for(lambda: rec.state is RecordingStatus.STOPPED)
        t0 = time.monotonic()
        rec.start(0)
        assert time.monotonic() - t0 < 0.01  # never blocks the engine
        assert wait_for(lambda: rec.state is RecordingStatus.STARTED)
        assert rec.status().online
    finally:
        rec.close()


def test_studio_shows_pearl_status_SE2(pearl: tuple[PearlHttp, FakePearlState]) -> None:
    from cutcut.app.studio import Studio, StudioDeps
    from cutcut.common.clock import FakeClock
    from cutcut.common.config import (
        example_site_dir,
        load_rule_presets,
        load_show_types,
        load_site,
    )
    from cutcut.core.runtime import RecordingExecutor

    client, _ = pearl
    rec = PearlRecorder(client, start_thread=False)
    rec.step()
    studio = Studio(
        StudioDeps(
            site=load_site(example_site_dir()),
            show_types=load_show_types(),
            presets=load_rule_presets(),
            clock=FakeClock(),
            executor=RecordingExecutor(),
            recorder=rec,
        )
    )
    info = studio.state().recording
    assert info.online
    assert info.firmware == "4.24.1"
    assert info.storage_free_pct == 70
