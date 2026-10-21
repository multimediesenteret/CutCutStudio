from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cutcut.api.app import create_app
from cutcut.common.clock import FakeClock
from cutcut.common.store import Store
from cutcut.core.runtime import TICK_MS
from cutcut.sim.live import SIM_PIN, build_live_sim, sim_routes

TEST_CARD = "04A1B2C3"  # fictional (sim/fakes.py)


class Rig:
    def __init__(self, tmp: Path, *, dev_admin: bool = True) -> None:
        self.clock = FakeClock()
        self.store = Store(tmp / "cutcut.db")
        self.sim, self.auth = build_live_sim(self.clock, store=self.store)
        self.auth.dev_admin = dev_admin
        self.app = create_app(
            self.sim.studio, self.auth, run_loop=False, extra_routes=sim_routes(self.sim)
        )
        self.client = TestClient(self.app)

    def run(self, ms: int) -> None:
        for _ in range(ms // TICK_MS):
            self.clock.advance(TICK_MS)
            self.sim.before_tick()
            self.sim.studio.tick()

    def state(self) -> dict:  # type: ignore[type-arg]
        r = self.client.get("/api/state")
        assert r.status_code == 200
        return r.json()  # type: ignore[no-any-return]


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def test_health_needs_no_sign_in(rig: Rig) -> None:
    rig.run(300)
    body = rig.client.get("/api/health").json()
    assert body["status"] in ("ok", "warn", "error")
    assert "engine" in body


def test_whole_touch_flow_from_card_to_done(rig: Rig) -> None:
    c = rig.client
    rig.run(500)
    assert rig.state()["touch"]["step"] == "idle"
    c.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(60)
    s = rig.state()
    assert s["touch"]["step"] == "ready"
    assert s["session"]["user"]["display_name"] == "Testkort A"
    assert c.put("/api/session/show", json={"guests": 2, "video": True}).status_code == 200
    rig.run(60)
    assert len(rig.state()["participants"]) == 3
    assert c.post("/api/recording", json={"action": "start"}).status_code == 200
    rig.run(1000)
    assert rig.state()["touch"]["step"] == "countdown"
    rig.run(3500)
    s = rig.state()
    assert s["touch"]["step"] == "rec"
    assert s["recording"]["pearl"] == "started"
    c.post("/api/sim/talk", json={"participant": "P2", "on": True})
    rig.run(6000)
    assert rig.state()["engine"]["program"] == "CU:P2"
    assert c.post("/api/recording", json={"action": "stop"}).status_code == 200
    rig.run(200)
    s = rig.state()
    assert s["touch"]["step"] == "done"
    assert s["session"]["recording"]["duration_s"] >= 6
    rig.run(31_000)
    assert rig.state()["touch"]["step"] == "idle"


def test_unknown_card_shows_notice(rig: Rig) -> None:
    rig.client.post("/api/sim/card", json={"card": "DEADBEEF"})
    rig.run(60)
    s = rig.state()
    assert s["touch"]["step"] == "idle"
    assert "ikke gjenkjent" in s["touch"]["notice"]


def test_logout_during_recording_is_refused_with_plain_message(rig: Rig) -> None:
    rig.client.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(60)
    rig.client.post("/api/recording", json={"action": "start"})
    rig.run(4500)
    r = rig.client.delete("/api/session")
    assert r.status_code == 409
    assert "opptaket pågår" in r.json()["detail"]


def test_start_from_touch_and_tech_gives_one_recording(rig: Rig) -> None:
    rig.client.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(60)
    rig.client.post("/api/recording", json={"action": "start"})
    rig.client.post("/api/recording", json={"action": "start"})
    rig.run(4500)
    assert rig.state()["touch"]["step"] == "rec"
    rig.client.post("/api/recording", json={"action": "stop"})
    rig.client.post("/api/recording", json={"action": "stop"})
    rig.run(200)
    assert rig.state()["touch"]["step"] == "done"


def test_override_cut_and_auto(rig: Rig) -> None:
    rig.run(3000)
    assert rig.client.post("/api/cut", json={"shot": "CU:P1"}).status_code == 200
    rig.run(60)
    assert rig.state()["engine"]["program"] == "CU:P1"
    assert rig.client.post("/api/auto", json={"on": False}).status_code == 200
    rig.run(60)
    assert rig.state()["engine"]["auto"] is False
    assert rig.client.post("/api/cut", json={"shot": "CU:P9"}).status_code == 422
    assert rig.client.post("/api/cut", json={"shot": "CU:P4"}).status_code == 409


def test_features_and_preset_change_live(rig: Rig) -> None:
    assert rig.client.post("/api/features", json={"bird": False}).status_code == 200
    assert rig.client.post("/api/preset", json={"preset": "energisk"}).status_code == 200
    rig.run(60)
    s = rig.state()
    assert s["rules"]["preset"] == "energisk"
    assert s["rules"]["features"]["bird"] is False
    assert rig.client.get("/api/rules").json()["values"]["T2_confirm_ms"] == 500
    assert rig.client.post("/api/features", json={"nope": True}).status_code == 409


def test_roles_touch_cannot_override(tmp_path: Path) -> None:
    rig = Rig(tmp_path, dev_admin=False)
    try:
        assert rig.client.get("/api/me").json()["role"] == "touch"
        assert rig.client.post("/api/auto", json={"on": False}).status_code == 403
        assert rig.client.post("/api/help").status_code == 200  # touch may ask for help
        # technician signs in with PIN → operator, can override but not change switches
        r = rig.client.post("/api/login", json={"username": "tekniker1", "pin": SIM_PIN})
        assert r.status_code == 200
        assert "httponly" in r.headers["set-cookie"].lower()
        assert "samesite=strict" in r.headers["set-cookie"].lower()
        assert rig.client.post("/api/auto", json={"on": False}).status_code == 200
        assert rig.client.post("/api/features", json={"bird": False}).status_code == 403
        assert (
            rig.client.post("/api/login", json={"username": "admin1", "pin": "0000"}).status_code
            == 401
        )
        assert (
            rig.client.post("/api/login", json={"username": "ukjent", "pin": SIM_PIN}).status_code
            == 401
        )
    finally:
        rig.store.close()


def test_other_machines_need_sign_in(tmp_path: Path) -> None:
    rig = Rig(tmp_path, dev_admin=False)
    try:
        remote = TestClient(rig.app, client=("10.10.10.77", 5000))
        assert remote.get("/api/state").status_code == 401
        assert remote.get("/api/health").status_code == 200
    finally:
        rig.store.close()


def test_websocket_sends_full_state_then_live_messages(rig: Rig) -> None:
    with rig.client.websocket_connect("/ws?topics=state,meters,decision") as ws:
        first = ws.receive_json()
        assert first["type"] == "state"
        assert first["full"] is True
        assert "engine" in first["data"]
        rig.client.post("/api/sim/talk", json={"participant": "P2", "on": True})
        rig.run(4000)
        kinds = {ws.receive_json()["type"] for _ in range(30)}
        assert {"meters", "state"} <= kinds


def test_card_number_never_appears_anywhere_I8(rig: Rig) -> None:
    c = rig.client
    c.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(60)
    c.post("/api/recording", json={"action": "start"})
    rig.run(5000)
    c.post("/api/recording", json={"action": "stop"})
    rig.run(500)
    rig.store.flush()
    blobs = [
        json.dumps(rig.state()),
        json.dumps(c.get("/api/log").json()),
        json.dumps(c.get("/api/health").json()),
    ]
    db = (
        rig.store.path.read_bytes() + Path(str(rig.store.path) + "-wal").read_bytes()
        if Path(str(rig.store.path) + "-wal").exists()
        else rig.store.path.read_bytes()
    )
    for card in (TEST_CARD, TEST_CARD.lower(), "C3B2A104", str(int(TEST_CARD, 16))):
        assert all(card not in b for b in blobs)
        assert card.encode() not in db


def test_audit_log_records_who_did_what(rig: Rig) -> None:
    rig.client.post("/api/auto", json={"on": False})
    rig.store.flush()
    assert rig.store.count("audit") >= 1


def test_openapi_reference_is_current() -> None:
    """docs/reference/openapi.json is generated (12.1): uv run python tools/gen_openapi.py"""
    from tools.gen_openapi import OUT, render

    assert OUT.read_text(encoding="utf-8") == render()
