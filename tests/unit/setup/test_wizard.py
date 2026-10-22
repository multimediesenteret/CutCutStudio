"""HS-5/HS-6: the setup helper on the technician screen. «Sjekk steget» runs the step's health
checks, «Godkjent» is stored with name and time, and «Fiks for meg» is refused during a
recording."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from cutcut.devices.atem.bridge import AtemBridgeClient
from cutcut.setup.multiview import atem_input_names
from tests.unit.api.test_api import TEST_CARD, Rig

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "atem" / "state-studio.json"


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def bridge(rig: Rig) -> list[dict[str, Any]]:
    """A real atem-bridge client fed the studio fixture; returns what it sends."""
    sent: list[dict[str, Any]] = []
    client = AtemBridgeClient(send=lambda _topic, p: sent.append(p), clock=lambda: 0.0)
    client.on_message("atem.state", json.loads(FIXTURE.read_text(encoding="utf-8")))
    rig.sim.studio.deps.atem = client
    return sent


def test_ten_steps_and_none_approved_at_first(rig: Rig) -> None:
    steps = rig.client.get("/api/setup/steps").json()
    assert [s["step"]["number"] for s in steps] == list(range(1, 11))
    assert all(s["approved"] is None for s in steps)
    assert steps[2]["step"]["fix"]["label"] == "Gi inngangene riktige navn"


def test_check_now_then_approve_with_name_and_time(rig: Rig) -> None:
    c = rig.client
    r = c.post("/api/setup/steps/pc/approve")
    assert r.status_code == 409
    assert "Sjekk steget" in r.json()["detail"]
    view = c.post("/api/setup/steps/pc/check").json()
    assert {x["id"] for x in view["results"]} >= {"H-PC-1", "H-PC-2", "H-PC-3"}
    assert view["state"] in {"green", "yellow"}
    approved = c.post("/api/setup/steps/pc/approve").json()
    assert approved["state"] in {"approved", "yellow"}  # yellow still shows the deviation
    assert approved["approved"]["by"] == "simulator"
    # kept: a new read still has it (and the database, for a restart)
    again = next(s for s in c.get("/api/setup/steps").json() if s["step"]["id"] == "pc")
    assert again["approved"]["by"] == "simulator"


def test_dress_rehearsal_is_approved_by_the_technician(rig: Rig) -> None:
    view = rig.client.post("/api/setup/steps/generalprove/approve").json()
    assert view["state"] == "approved"


def test_unknown_step(rig: Rig) -> None:
    r = rig.client.post("/api/setup/steps/kaffe/check")
    assert r.status_code == 409
    assert "Ukjent setup-steg" in r.json()["detail"]


def test_expected_input_names() -> None:
    from cutcut.common.config import default_config_dir, load_site

    site = load_site(default_config_dir().parent / "site" / "multimediesenteret")
    names = atem_input_names(site)
    assert names[1] == "C1"
    assert names[6] == "BIRD"
    assert names[7] == "LAPTOP"


def test_fix_names_the_inputs_and_nothing_else(rig: Rig) -> None:
    c = rig.client
    blocked = c.get("/api/setup/steps").json()[2]
    assert blocked["fix_available"] is False  # no ATEM in the simulator
    assert "ATEM kan ikke leses" in blocked["fix_blocked"]
    sent = bridge(rig)
    assert c.get("/api/setup/steps").json()[2]["fix_available"] is True
    assert c.post("/api/setup/steps/atem/fix").status_code == 200
    ops = {p["op"] for p in sent}
    assert ops == {"input_name"}  # never cut or preview (I2)
    named = {p["args"]["input"]: p["args"]["long"] for p in sent}
    assert named == atem_input_names(rig.sim.studio.deps.site)  # every name in the fixture is wrong
    assert "BIRD" in named.values()
    assert all(len(p["args"]["short"]) <= 4 for p in sent)


def test_fix_is_refused_during_a_recording(rig: Rig) -> None:
    c = rig.client
    sent = bridge(rig)
    c.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(60)
    c.put("/api/session/show", json={"guests": 1, "video": True})
    c.post("/api/recording", json={"action": "start"})
    rig.run(4500)
    r = c.post("/api/setup/steps/atem/fix")
    assert r.status_code == 409
    assert "opptak" in r.json()["detail"]
    assert sent == []
