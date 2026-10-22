"""The whole chain in one process (M2): core with Companion, Pearl and the bus, against fakes.

audio-capture and atem-bridge are stood in for by a ZeroMQ publisher sending the same
messages they send (the ATEM message is the shared contract fixture). Companion and Pearl
are fake HTTP servers. Nothing here is simulated inside core: it is the studio code path.
"""

from __future__ import annotations

import json
import shutil
import socket
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import zmq
from fastapi.testclient import TestClient

from cutcut.app.core import CoreOptions, build_core
from cutcut.common.platform.secrets import FakeSecretStore
from cutcut.sim.fake_companion import FakeCompanionState, fake_companion
from cutcut.sim.fake_pearl import FakePearlState, fake_pearl

ROOT = Path(__file__).resolve().parents[2]
ATEM = json.loads((ROOT / "tests" / "fixtures" / "atem" / "state-studio.json").read_text())
PIN = "4711"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def site_copy(tmp: Path, companion_url: str, pearl_url: str) -> Path:
    site = tmp / "site"
    shutil.copytree(ROOT / "site" / "multimediesenteret", site)
    host, port = pearl_url.removeprefix("http://").split(":")
    devices = (site / "devices.yaml").read_text()
    devices = devices.replace(
        'companion: { url: "http://127.0.0.1:8000"', f'companion: {{ url: "{companion_url}"'
    )
    devices = devices.replace(
        "pearl: { ip: 10.10.10.30,", f"pearl: {{ ip: {host}, port: {port}, scheme: http,"
    )
    (site / "devices.yaml").write_text(devices)
    (site / "staff.yaml").write_text(
        "schema_version: 1\noperators: [tekniker1]\nadmins: [admin1]\n"
    )
    return site


class Bus:
    """Plays audio-capture and atem-bridge: publishes into core's events-in socket."""

    def __init__(self, port: int) -> None:
        self.ctx = zmq.Context()
        self.port = port
        self.sock = self.ctx.socket(zmq.PUB)
        self.sock.connect(f"tcp://127.0.0.1:{port}")
        self.seq: dict[str, int] = {}

    def send(self, topic: str, source: str, payload: dict[str, Any]) -> None:
        seq = self.seq.get(topic, 0)
        self.seq[topic] = seq + 1
        msg = {
            "topic": topic,
            "source": source,
            "ts": datetime.now(UTC).isoformat(),
            "mono_ms": int(time.monotonic() * 1000),
            "seq": seq,
            "schema_version": 1,
            "payload": payload,
        }
        self.sock.send_multipart([topic.encode(), json.dumps(msg).encode()])

    def close(self) -> None:
        self.sock.close(0)
        self.ctx.term()


def core_out_port(core: Any) -> int:
    return int(core.bus_out_port)


def talk(mic: str | None) -> dict[str, Any]:
    on = {"vad": 0.95, "level_db": -20, "dominance_db": 15, "pause_ms": 0}
    off = {"vad": 0.02, "level_db": -60, "dominance_db": -15, "pause_ms": 5000}
    return {"mics": {m: on if m == mic else off for m in ("M1", "M2", "M3", "M4")}}


def until(cond: Callable[[], bool], timeout: float, tick: Callable[[], None] | None = None) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if tick:
            tick()
        if cond():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def rig(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, Bus, FakeCompanionState, FakePearlState, Any]]:
    with fake_companion() as (curl, cstate), fake_pearl() as (purl, pstate):
        bus_in, bus_out = free_port(), free_port()
        core = build_core(
            CoreOptions(
                site_dir=site_copy(tmp_path, curl, purl),
                data_dir=tmp_path / "data",
                secrets=FakeSecretStore(
                    {"pearl_password": "test-only", "operator_pin": PIN, "admin_pin": PIN}
                ),
                bus_in_port=bus_in,
                bus_out_port=bus_out,
            )
        )
        bus = Bus(bus_in)
        core.bus_out_port = bus_out  # type: ignore[attr-defined]  # for tests listening to core
        try:
            with TestClient(core.app) as client:
                yield client, bus, cstate, pstate, core
        finally:
            bus.close()
            core.close()


def test_core_reads_the_atem_cuts_via_companion_and_records_on_pearl(
    rig: tuple[TestClient, Bus, FakeCompanionState, FakePearlState, Any],
) -> None:
    client, bus, cstate, pstate, core = rig
    assert client.post("/api/login", json={"username": "tekniker1", "pin": PIN}).status_code == 200

    # atem-bridge reports the ATEM; core sees it (and its multiview) within a moment.
    def atem() -> None:
        bus.send("atem.state", "atem-bridge", ATEM)

    assert until(lambda: core.bridge.readback() is not None, 5, atem)
    mv = client.get("/api/setup/multiview").json()
    assert mv["readback"]["windows"][4] == "input6"
    assert mv["ok"] is True

    # A technician starts a session and a recording; Pearl is asked and confirms.
    assert client.post("/api/session", json={"username": "kanordm"}).status_code == 200
    assert client.post("/api/recording", json={"action": "start"}).status_code == 200
    assert until(lambda: ("1", "start") in pstate.commands, 8, atem)
    assert until(lambda: client.get("/api/state").json()["touch"]["step"] == "rec", 8, atem)
    assert client.get("/api/state").json()["recording"]["online"] is True

    # audio-capture says gjest 1 talks: core puts Camera 2 on preview and takes it via Companion.
    def speak() -> None:
        atem()
        bus.send("audio.frame", "audio-capture", talk("M2"))

    assert until(lambda: (10, 3, 0) in cstate.presses and (10, 0, 1) in cstate.presses, 15, speak)
    assert cstate.variables.get("regi_shot")

    assert client.post("/api/recording", json={"action": "stop"}).status_code == 200
    assert until(lambda: ("1", "stop") in pstate.commands, 5, atem)


def test_core_starts_without_any_equipment(tmp_path: Path) -> None:
    """Uptime first: nothing answers, the studio still starts and shows it."""
    site = site_copy(tmp_path, "http://127.0.0.1:9", "http://127.0.0.1:9")
    core = build_core(
        CoreOptions(
            site_dir=site,
            data_dir=tmp_path / "data",
            secrets=FakeSecretStore({}),
            bus_in_port=free_port(),
            bus_out_port=free_port(),
        )
    )
    try:
        with TestClient(core.app) as client:
            assert client.get("/api/health").status_code == 200
            assert core.bridge.readback() is None
    finally:
        core.close()


def test_core_shows_processes_from_the_supervisor(
    rig: tuple[TestClient, Bus, FakeCompanionState, FakePearlState, Any],
) -> None:
    """SO-1: the supervisor's status reaches Helse, and a process that is down gives H-PROC."""
    from cutcut.supervisor.report import StatusReporter

    client, bus, _, _, core = rig
    reporter = StatusReporter(port=bus.port)
    down = [
        {"name": "core", "running": True, "uptime_s": 12, "restarts_10min": 0},
        {
            "name": "atem-bridge",
            "running": False,
            "restarts_10min": 1,
            "last_reason": "avsluttet med kode 1",
        },
    ]
    try:
        assert until(
            lambda: any(a.code == "H-PROC-atem-bridge" for a in core.studio.alerts),
            5,
            lambda: reporter(down),
        )
        procs = client.get("/api/health").json()["runtime"]["processes"]
        assert [p["name"] for p in procs] == ["core", "atem-bridge"]
        assert procs[1]["running"] is False

        up = [dict(down[0]), {**down[1], "running": True}]

        def check(cid: str) -> str | None:
            return next((r.status for r in core.studio.health.results() if r.id == cid), None)

        assert until(lambda: check("H-PROC-atem-bridge") == "green", 5, lambda: reporter(up))
        assert check("H-PROC-core") == "green"
        assert check("H-PROC-supervisor") == "green"
    finally:
        reporter.close()


def test_core_checks_companion_pages_and_pearl(
    rig: tuple[TestClient, Bus, FakeCompanionState, FakePearlState, Any],
) -> None:
    """HS-2 against the fake devices: Companion without CutCut's pages is red, with them green;
    Pearl's storage is read in minutes."""
    client, _, cstate, _, core = rig

    def check(cid: str) -> dict[str, Any] | None:
        rows = client.get("/api/health/checks").json()
        return next((r for r in rows if r["id"] == cid), None)

    assert until(lambda: (check("H-COMP-1") or {}).get("status") == "red", 10)
    assert check("H-COMP-1")["value"] == "ingen CutCut-sider"  # type: ignore[index]
    cstate.variables["cutcut_pages_version"] = "1"
    assert until(lambda: (check("H-COMP-1") or {}).get("status") == "green", 10)

    assert until(lambda: (check("H-PRL-1") or {}).get("status") == "green", 10)
    assert check("H-PRL-1")["value"].endswith("min ledig")  # type: ignore[index]
    assert {"H-PC-1", "H-PC-2", "H-PC-3"} <= {r.id for r in core.studio.health.results()}


def test_companion_down_the_cut_goes_through_atem_bridge_S5(
    rig: tuple[TestClient, Bus, FakeCompanionState, FakePearlState, Any],
) -> None:
    """DA-7 end to end: Companion stops answering; the technician's cut still reaches the
    ATEM, as an ``atem.cmd`` for atem-bridge on the bus."""
    client, bus, cstate, _, core = rig
    out_ctx = zmq.Context()
    sub = out_ctx.socket(zmq.SUB)
    sub.setsockopt(zmq.SUBSCRIBE, b"atem.cmd")
    sub.connect(f"tcp://127.0.0.1:{core_out_port(core)}")
    try:
        assert (
            client.post("/api/login", json={"username": "tekniker1", "pin": PIN}).status_code == 200
        )
        until(
            lambda: core.bridge.readback() is not None,
            5,
            lambda: bus.send("atem.state", "atem-bridge", ATEM),
        )
        cstate.fail = True
        got: list[dict[str, Any]] = []

        def cut_and_listen() -> None:
            bus.send("atem.state", "atem-bridge", ATEM)
            if not got:
                client.post("/api/cut", json={"shot": "CU:P2"})
            while sub.poll(10):
                got.append(json.loads(sub.recv_multipart()[1])["payload"])

        assert until(lambda: any(g.get("op") == "cut" for g in got), 15, cut_and_listen)
        cut = next(g for g in got if g.get("op") == "cut")
        assert cut["args"] == {"input": 2}  # Camera 2 = gjest 1 (D-054)
    finally:
        sub.close(0)
        out_ctx.term()


def test_missing_layout_macros_block_the_layout_switch_DA7(
    rig: tuple[TestClient, Bus, FakeCompanionState, FakePearlState, Any],
) -> None:
    client, bus, _, _, core = rig
    assert client.post("/api/login", json={"username": "admin1", "pin": PIN}).status_code == 200
    assert until(
        lambda: core.bridge.macros() is not None,
        5,
        lambda: bus.send("atem.state", "atem-bridge", ATEM),  # the fixture lacks most macros
    )
    r = client.post("/api/features", json={"layouts": True})
    assert r.status_code == 409
    assert "Makro 11 PIP_P2_CONTENT mangler" in r.json()["detail"]


def test_core_hears_the_video_layer_H_VID_1(
    rig: tuple[TestClient, Bus, FakeCompanionState, FakePearlState, Any],
) -> None:
    """VI-1: vision.status and vision.frame reach core; H-VID-1 appears once vision reports."""
    client, bus, _, _, core = rig
    assert not any(r.id == "H-VID-1" for r in core.studio.health.results())

    def send() -> None:
        bus.send("vision.status", "vision", {"source": "syntetisk", "fps": 15, "frames": 30})
        bus.send("vision.frame", "vision", {"tiles": [{"tile": "W1", "signal": True}]})

    def check() -> str | None:
        rows = client.get("/api/health/checks").json()
        return next((r["status"] for r in rows if r["id"] == "H-VID-1"), None)

    assert until(lambda: check() == "green", 10, send)
    assert core.studio.runtime.vision_frame["tiles"][0]["tile"] == "W1"


def test_program_window_disagrees_with_the_atem_H_VID_3(
    rig: tuple[TestClient, Bus, FakeCompanionState, FakePearlState, Any],
) -> None:
    """VI-3: the ATEM says Camera 2 on program, the program window looks like Camera 3."""
    client, bus, _, _, _ = rig
    state = {**ATEM, "program_input": 2}
    seen = {"source": "C3"}

    def send() -> None:
        bus.send("atem.state", "atem-bridge", state)
        bus.send("vision.status", "vision", {"source": "syntetisk", "fps": 15})
        bus.send("vision.frame", "vision", {"tiles": []})
        bus.send("vision.pgm", "vision", {**seen, "score": 0.05})

    def check() -> str | None:
        rows = client.get("/api/health/checks").json()
        return next((r["status"] for r in rows if r["id"] == "H-VID-3"), None)

    assert until(lambda: check() == "yellow", 15, send)
    seen["source"] = "C2"
    assert until(lambda: check() == "green", 10, send)


def test_atem_as_set_up_and_its_iso_disk_H_ATEM_2_H_ATEM_4(
    rig: tuple[TestClient, Bus, FakeCompanionState, FakePearlState, Any],
) -> None:
    """HS-7: the ATEM's format, input names and AUX against the approved fasit, and its disk."""
    client, bus, _, _, _ = rig
    assert client.post("/api/login", json={"username": "admin1", "pin": PIN}).status_code == 200
    state = json.loads(json.dumps(ATEM))

    def send() -> None:
        bus.send("atem.state", "atem-bridge", state)
        time.sleep(0.2)
        client.post("/api/health/morning-check")  # every check now, not on its interval

    def check(cid: str) -> dict[str, Any] | None:
        rows = client.get("/api/health/checks").json()
        return next((r for r in rows if r["id"] == cid), None)

    assert until(lambda: (check("H-ATEM-4") or {}).get("value") == "90 min", 10, send)
    assert until(lambda: (check("H-ATEM-2") or {}).get("value") == "1080p50", 10, send)
    got = check("H-ATEM-2")
    assert got is not None
    assert got["status"] == "green"
    assert "Ingen ATEM-fasit" in got["message"]

    r = client.post("/api/setup/atem/fasit")
    assert r.status_code == 200
    assert r.json()["fasit"]["input_names"] == {"1": "Camera 1", "2": "Camera 2", "6": "Camera 6"}
    assert r.json()["iso"]["disk"] == "ISO-SSD"

    state["inputs"][1]["long"] = "Gjest"  # someone renames input 2 on the ATEM
    state["iso"]["time_available_s"] = 1200
    assert until(lambda: (check("H-ATEM-2") or {}).get("status") == "yellow", 10, send)
    got = check("H-ATEM-2")
    assert got is not None
    assert "inngang 2 heter «Gjest», ikke «Camera 2»" in got["message"]
    assert until(lambda: (check("H-ATEM-4") or {}).get("status") == "yellow", 10, send)
