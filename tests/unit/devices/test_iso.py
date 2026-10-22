"""DA-8 (spec 7.7): ISO recording on the ATEM's disk. Started from the technician window or with
Pearl when the show type records ISO; stopped only by a person (I7)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from cutcut.devices.atem import iso
from cutcut.devices.atem.bridge import AtemBridgeClient
from tests.unit.api.test_api import TEST_CARD, Rig

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "atem" / "state-studio.json"


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def start_session(rig: Rig) -> None:
    c = rig.client
    c.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(60)
    c.put("/api/session/show", json={"guests": 1, "video": True})
    c.post("/api/recording", json={"action": "start"})
    rig.run(4500)


def iso_state(rig: Rig) -> dict[str, Any]:
    return rig.state()["recording"]["iso"]  # type: ignore[no-any-return]


def test_file_name_is_the_session_name() -> None:
    when = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
    assert iso.filename(when, "podcast", "ola.nordmann") == "2026-10-22_podcast_ola.nordmann"
    assert iso.filename(when, "kun-lyd", None) == "2026-10-22_kun-lyd_tekniker"
    assert iso.filename(when, "panel", "æ ø/å") == "2026-10-22_panel_-----"


def test_start_and_stop_from_the_technician_window(rig: Rig) -> None:
    c = rig.client
    st = iso_state(rig)
    assert st["available"] is True
    assert st["state"] == "idle"
    assert st["disk"] == "ISO-SSD"
    start_session(rig)
    assert c.post("/api/recording/iso", json={"action": "start"}).status_code == 200
    rig.run(3000)
    st = iso_state(rig)
    assert st["state"] == "recording"
    assert st["filename"].endswith("_podcast_" + rig.state()["session"]["user"]["username"])
    assert st["duration_s"] >= 2
    r = c.post("/api/recording/iso", json={"action": "start"})
    assert r.status_code == 409
    assert "går allerede" in r.json()["detail"]
    assert c.post("/api/recording/iso", json={"action": "stop"}).status_code == 200
    assert iso_state(rig)["state"] == "idle"


def test_stopping_pearl_never_stops_iso(rig: Rig) -> None:
    c = rig.client
    start_session(rig)
    c.post("/api/recording/iso", json={"action": "start"})
    c.post("/api/recording", json={"action": "stop"})
    rig.run(500)
    assert rig.sim.atem.iso_state == "recording"  # I7
    alerts = rig.state()["alerts"]
    assert any(a["code"] == "ISO" and "går fortsatt" in a["message"] for a in alerts)


def test_the_show_type_starts_iso_with_pearl(rig: Rig) -> None:
    studio = rig.sim.studio
    types = studio.deps.show_types.types
    patched = {**types, "podcast": types["podcast"].model_copy(update={"iso_record": True})}
    studio.deps.show_types = studio.deps.show_types.model_copy(update={"types": patched})
    assert iso_state(rig)["wanted"] is True
    start_session(rig)
    assert rig.sim.atem.iso_state == "recording"
    assert iso_state(rig)["started_by"] == "automatisk (show-type)"


def test_no_disk_is_refused_and_pearl_records_anyway(rig: Rig) -> None:
    rig.sim.atem.iso_disk = None
    r = rig.client.post("/api/recording/iso", json={"action": "start"})
    assert r.status_code == 409
    assert "ingen disk" in r.json()["detail"]
    studio = rig.sim.studio
    types = studio.deps.show_types.types
    patched = {**types, "podcast": types["podcast"].model_copy(update={"iso_record": True})}
    studio.deps.show_types = studio.deps.show_types.model_copy(update={"types": patched})
    start_session(rig)
    s = rig.state()
    assert s["recording"]["pearl"] == "started"
    assert any(a["code"] == "H-ATEM-4" for a in s["alerts"])


def test_the_bridge_client_sends_iso_commands() -> None:
    sent: list[dict[str, Any]] = []
    client = AtemBridgeClient(send=lambda _t, p: sent.append(p), clock=lambda: 0.0)
    assert client.iso_status() is None
    assert client.iso_start("x") is False  # not connected
    client.on_message("atem.state", json.loads(FIXTURE.read_text(encoding="utf-8")))
    st = client.iso_status()
    assert st is not None
    assert st.state == "idle"
    assert st.disk == "ISO-SSD"
    assert client.iso_start("2026-10-22_podcast_ola")
    assert client.iso_stop()
    assert [(p["op"], p["args"]) for p in sent] == [
        ("iso_start", {"filename": "2026-10-22_podcast_ola"}),
        ("iso_stop", {}),
    ]
