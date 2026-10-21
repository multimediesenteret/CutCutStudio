"""DA-5: the ATEM/Companion machine test against core, a fake Companion and a simulated ATEM
that answers Companion's button presses over the bus, like atem-bridge does."""

from __future__ import annotations

import copy
import threading
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cutcut.common.config import load_site
from cutcut.common.ids import SourceId
from cutcut.devices.atem.macros import LAYOUT_MACROS
from cutcut.devices.companion.client import CompanionHttp
from cutcut.hwtest.atem import AtemTest
from cutcut.sim.fake_companion import FakeCompanionState
from cutcut.sim.fake_pearl import FakePearlState
from tests.integration.test_core import ATEM, PIN, Bus, until
from tests.integration.test_core import rig as rig

Rig = tuple[TestClient, Bus, FakeCompanionState, FakePearlState, Any]


class Atem(threading.Thread):
    """Reads Companion's presses on page 10 and reports the new state, 25 times a second."""

    def __init__(self, bus: Bus, cstate: FakeCompanionState, core: Any, *, wrong: bool = False):
        super().__init__(daemon=True)
        self.bus, self.cstate, self.core = bus, cstate, core
        self.state = copy.deepcopy(ATEM)
        self.state["macros"] = [{"number": m.number, "name": m.name} for m in LAYOUT_MACROS]
        site = core.studio.deps.site
        cmap = site.companion_map
        from cutcut.devices.atem.bridge import SUPERSOURCE, site_input_map

        inputs = {s: n for n, s in site_input_map(list(site.shows.values())).items()}
        inputs[SourceId.SUPERSOURCE] = SUPERSOURCE
        self.buttons = {(10, b.row, b.col): inputs.get(src) for src, b in cmap.preview.items()}
        if wrong:  # someone moved a button in Companion: C2 sets input 3
            key = next(k for k, v in self.buttons.items() if v == 2)
            self.buttons[key] = 3
        self.take = (10, cmap.take_cut.row, cmap.take_cut.col)
        self.stop = threading.Event()
        self.seen = 0

    def run(self) -> None:
        while not self.stop.is_set():
            for press in self.cstate.presses[self.seen :]:
                self.seen += 1
                if press == self.take:
                    s = self.state
                    s["program_input"], s["preview_input"] = s["preview_input"], s["program_input"]
                elif self.buttons.get(press) is not None:
                    self.state["preview_input"] = self.buttons[press]
            self.bus.send("atem.state", "atem-bridge", self.state)
            self.stop.wait(0.04)


class Technician:
    def __init__(self, take: bool) -> None:
        self.take = take
        self.said: list[str] = []

    def say(self, text: str) -> None:
        self.said.append(text)

    def wait(self, text: str) -> bool:
        self.said.append(text)
        return self.take or not text.startswith("B6")


@pytest.fixture
def setup(rig: Rig) -> tuple[Rig, FakeCompanionState]:
    client, _, cstate, _, _ = rig
    assert client.post("/api/login", json={"username": "tekniker1", "pin": PIN}).status_code == 200
    cstate.variables["cutcut_pages_version"] = "1"
    return rig, cstate


def run(rig: Rig, *, take: bool = False, wrong: bool = False) -> AtemTest:
    client, bus, cstate, _, core = rig
    atem = Atem(bus, cstate, core, wrong=wrong)
    atem.start()
    try:
        import time

        deadline = time.monotonic() + 5
        while client.get("/api/setup/atem").json()["connected"] is not True:
            assert time.monotonic() < deadline
            time.sleep(0.05)
        site = load_site(core.studio.deps.site.root)
        url = str(core.companion.api._http.base_url)
        test = AtemTest(site, client, CompanionHttp(url), Technician(take))
        test.run()
        return test
    finally:
        atem.stop.set()
        atem.join(2)


def results(test: AtemTest) -> dict[str, str]:
    return {s.id: s.result for s in test.report.steps}


def test_a_studio_that_is_set_up_right_passes(setup: tuple[Rig, FakeCompanionState]) -> None:
    rig, _ = setup
    test = run(rig, take=True)
    # B2: the studio's multiview has safe area on (the photo, D-053): a warning, not an error.
    assert results(test) == {
        "B1": "ok",
        "B2": "advarsel",
        "B3": "ok",
        "B4": "ok",
        "B5": "ok",
        "B6": "ok",
    }
    steps = {s.id: s for s in test.report.steps}
    assert "safe" in steps["B2"].summary.lower() or "sikker" in steps["B2"].summary.lower()
    assert steps["B1"].summary.startswith("TelevisionStudioHD8ISO, 1080p50")
    assert steps["B5"].details["C2"]["input"] == 2
    assert (
        steps["B6"].details["after"]["program_input"]
        == steps["B6"].details["before"]["preview_input"]
    )
    # The engine was locked while buttons were pressed, and released after.
    assert until(lambda: rig[0].get("/api/state").json()["engine"]["lock"] is False, 3)


def test_a_wrong_button_and_a_skipped_take(setup: tuple[Rig, FakeCompanionState]) -> None:
    rig, _ = setup
    test = run(rig, wrong=True)
    got = results(test)
    assert got["B5"] == "feil"
    assert got["B6"] == "hoppet over"
    b5 = next(s for s in test.report.steps if s.id == "B5")
    assert "C2" in b5.summary
    assert "ga inngang 3, ikke 2" in b5.summary


def test_companion_without_cutcut_pages(setup: tuple[Rig, FakeCompanionState]) -> None:
    rig, cstate = setup
    del cstate.variables["cutcut_pages_version"]
    test = run(rig)
    b4 = next(s for s in test.report.steps if s.id == "B4")
    assert b4.result == "feil"
    assert "ikke importert" in b4.summary
