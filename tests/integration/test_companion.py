"""DA-3, DA-4, SIM-3: Companion client and executor against a fake Companion over HTTP."""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest

from cutcut.common.config import example_site_dir, load_site
from cutcut.common.ids import SourceId
from cutcut.core.intents import (
    DirectCut,
    Intent,
    PrepareLayout,
    SetCompanionVariable,
    SetPreview,
    ShowAudioOnly,
    Take,
)
from cutcut.devices.companion.client import CompanionError, CompanionHttp
from cutcut.devices.companion.executor import FAILS_TO_OPEN, OPEN_S, CompanionExecutor
from cutcut.sim.fake_companion import FakeCompanionState, fake_companion

CMAP = load_site(example_site_dir()).companion_map


@dataclass
class Clock:
    t: float = 1000.0

    def __call__(self) -> float:
        return self.t


@dataclass
class Bridge:
    intents: list[Intent] = field(default_factory=list)

    def submit(self, intent: Intent) -> None:
        self.intents.append(intent)


@pytest.fixture
def companion() -> Iterator[tuple[CompanionHttp, FakeCompanionState]]:
    with fake_companion() as (url, state):
        client = CompanionHttp(url)
        yield client, state
        client.close()


def drain(ex: CompanionExecutor) -> None:
    while ex.step():
        pass


def test_client_press_variables_and_connections(
    companion: tuple[CompanionHttp, FakeCompanionState],
) -> None:
    client, state = companion
    client.press(10, 0, 2)
    client.set_var("regi_reason", "Gjest 1 aktiv 1,2 s – æøå & ?")
    assert state.presses == [(10, 0, 2)]
    assert client.get_var("regi_reason") == "Gjest 1 aktiv 1,2 s – æøå & ?"
    assert client.get_var("finnes_ikke") is None
    [conn] = client.connections()
    assert conn.ok
    assert conn.module == "bmd-atem"


def test_pages_version(companion: tuple[CompanionHttp, FakeCompanionState]) -> None:
    client, state = companion
    assert client.pages_version() is None
    state.variables["cutcut_pages_version"] = "1"
    assert client.pages_version() == 1


def test_client_times_out_quickly() -> None:
    with fake_companion(FakeCompanionState(delay_s=1.0)) as (url, _):
        client = CompanionHttp(url)
        t0 = time.monotonic()
        with pytest.raises(CompanionError):
            client.press(10, 0, 0)
        assert time.monotonic() - t0 < 0.9
        client.close()


def test_intents_press_the_mapped_buttons(
    companion: tuple[CompanionHttp, FakeCompanionState],
) -> None:
    client, state = companion
    ex = CompanionExecutor(client, CMAP, start_thread=False)
    ex.submit(SetPreview(SourceId.C2))
    drain(ex)
    ex.submit(Take("cut"))
    ex.submit(PrepareLayout("QUAD4"))
    drain(ex)
    ex.submit(Take("mix"))
    ex.submit(DirectCut(SourceId.C5))
    ex.submit(ShowAudioOnly())
    drain(ex)
    assert state.presses == [
        (10, 0, 1),  # C2 to preview
        (10, 3, 0),  # TAKE CUT
        (10, 2, 6),  # QUAD4
        (10, 3, 1),  # TAKE MIX
        (11, 2, 4),  # direct C5 on the operator page
        (11, 3, 0),  # Kun lyd
    ]


def test_latest_preview_wins(companion: tuple[CompanionHttp, FakeCompanionState]) -> None:
    client, state = companion
    ex = CompanionExecutor(client, CMAP, start_thread=False)
    ex.submit(SetPreview(SourceId.C1))
    ex.submit(SetPreview(SourceId.C3))
    ex.submit(Take("cut"))
    ex.submit(SetPreview(SourceId.C4))  # after the take: kept, the take stays in order
    drain(ex)
    # C1 was superseded by C3; C3 stays before the TAKE so the TAKE cuts to C3.
    assert state.presses == [(10, 0, 2), (10, 3, 0), (10, 0, 3)]
    assert ex.status().dropped == 1


def test_take_is_never_reordered_before_its_preview(
    companion: tuple[CompanionHttp, FakeCompanionState],
) -> None:
    client, state = companion
    ex = CompanionExecutor(client, CMAP, start_thread=False)
    ex.submit(SetPreview(SourceId.C1))
    ex.submit(Take("cut"))
    drain(ex)
    assert state.presses == [(10, 0, 0), (10, 3, 0)]


def test_variables_are_coalesced_and_rate_limited(
    companion: tuple[CompanionHttp, FakeCompanionState],
) -> None:
    client, state = companion
    clock = Clock()
    ex = CompanionExecutor(client, CMAP, start_thread=False, clock=clock)
    for i in range(10):
        ex.submit(SetCompanionVariable("regi_shot", f"CU:P{i % 4 + 1}"))
    ex.submit(SetCompanionVariable("regi_rule", "T1"))
    assert ex.step()
    assert not ex.step()  # second variable waits for the 200 ms interval
    clock.t += 0.25
    assert ex.step()
    assert state.variables == {"regi_shot": "CU:P2", "regi_rule": "T1"}


def test_S5_companion_down_opens_the_breaker_and_cuts_via_bridge() -> None:
    clock = Clock()
    bridge = Bridge()
    with fake_companion(FakeCompanionState(fail=True)) as (url, state):
        client = CompanionHttp(url)
        ex = CompanionExecutor(client, CMAP, fallback=bridge, start_thread=False, clock=clock)
        for _ in range(FAILS_TO_OPEN):
            ex.submit(SetPreview(SourceId.C2))
            drain(ex)
        assert not ex.status().ok
        # While down: preview is remembered, TAKE becomes a direct cut through the bridge.
        ex.submit(SetPreview(SourceId.C3))
        ex.submit(Take("cut"))
        assert bridge.intents == [DirectCut(SourceId.C3)]
        assert ex.status().reserve_cuts == 1
        # Layouts are not possible on the reserve path.
        ex.submit(PrepareLayout("QUAD4"))
        ex.submit(Take("mix"))
        assert bridge.intents == [DirectCut(SourceId.C3)]
        # Companion comes back: after the open period, presses go through again.
        state.fail = False
        clock.t += OPEN_S + 0.1
        assert ex.status().ok
        ex.submit(SetPreview(SourceId.C4))
        drain(ex)
        assert state.presses[-1] == (10, 0, 3)
        client.close()


def test_worker_thread_sends_without_blocking_the_engine() -> None:
    with fake_companion(FakeCompanionState(delay_s=0.05)) as (url, state):
        client = CompanionHttp(url)
        ex = CompanionExecutor(client, CMAP)
        t0 = time.monotonic()
        for _ in range(20):
            ex.submit(SetPreview(SourceId.C1))
        assert time.monotonic() - t0 < 0.02  # submit only queues
        deadline = time.monotonic() + 3
        while not state.presses and time.monotonic() < deadline:
            time.sleep(0.01)
        ex.close()
        client.close()
        assert state.presses[0] == (10, 0, 0)
        assert len(state.presses) < 20  # superseded presses were never sent
