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
    assert c.post("/api/touch/again").status_code == 200
    rig.run(60)
    s = rig.state()
    assert s["touch"]["step"] == "ready"
    assert s["session"]["show"]["guests"] == 2
    assert c.post("/api/touch/again").status_code == 409  # only from the done screen
    assert c.delete("/api/session").status_code == 200
    rig.run(60)
    assert rig.state()["touch"]["step"] == "idle"


def test_done_screen_logs_out_by_itself(rig: Rig) -> None:
    c = rig.client
    c.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(60)
    c.post("/api/recording", json={"action": "start"})
    rig.run(5000)
    c.post("/api/recording", json={"action": "stop"})
    rig.run(200)
    assert rig.state()["touch"]["step"] == "done"
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


def test_fine_tuning_changes_live_and_resets_to_preset(rig: Rig) -> None:
    c = rig.client
    assert c.post("/api/rules/overrides", json={"T2_confirm_ms": 1100}).status_code == 200
    rules = c.get("/api/rules").json()
    assert rules["values"]["T2_confirm_ms"] == 1100
    assert rules["preset_values"]["T2_confirm_ms"] == 800
    assert rules["limits"]["T2_confirm_ms"] == {"type": "integer", "min": 100, "max": 5000}
    rig.run(150)
    assert rig.state()["rules"]["overrides"] == {"T2_confirm_ms": 1100}
    # The override survives a preset change: it is fine tuning on top of any preset.
    c.post("/api/preset", json={"preset": "rolig"})
    assert c.get("/api/rules").json()["values"]["T2_confirm_ms"] == 1100
    r = c.post("/api/rules/overrides", json={"T2_confirm_ms": 50})
    assert r.status_code == 409
    assert "T2_confirm_ms" in r.json()["detail"]
    assert c.post("/api/rules/overrides", json={"nope": 1}).status_code == 409
    assert c.post("/api/rules/overrides", json={"T2_confirm_ms": None}).status_code == 200
    assert c.get("/api/rules").json()["values"]["T2_confirm_ms"] == 1200  # rolig


def test_tuning_survives_a_restart(tmp_path: Path) -> None:
    """The studio runs unattended: a restart keeps the technician's preset and tuning."""
    first = Rig(tmp_path)
    first.client.post("/api/preset", json={"preset": "energisk"})
    first.client.post("/api/features", json={"bird": False})
    first.client.post("/api/rules/overrides", json={"T3_min_shot_s": 3.5})
    first.store.close()
    second = Rig(tmp_path)
    try:
        s = second.state()
        assert s["rules"]["preset"] == "energisk"
        assert s["rules"]["features"]["bird"] is False
        assert s["rules"]["overrides"] == {"T3_min_shot_s": 3.5}
        assert second.client.get("/api/rules").json()["values"]["T3_min_shot_s"] == 3.5
    finally:
        second.store.close()


def test_broken_saved_tuning_is_ignored(tmp_path: Path) -> None:
    first = Rig(tmp_path)
    first.store.put_kv("studio.tuning", {"overrides": {"T2_confirm_ms": -5}}, first.clock.now())
    first.store.close()
    second = Rig(tmp_path)
    try:
        assert second.state()["rules"]["overrides"] == {}
    finally:
        second.store.close()


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


def _one_recording(rig: Rig, guests: int = 1) -> None:
    c = rig.client
    c.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(60)
    c.put("/api/session/show", json={"guests": guests, "video": True})
    c.post("/api/recording", json={"action": "start"})
    rig.run(4500)
    c.post("/api/sim/talk", json={"participant": "P2", "on": True})
    rig.run(6000)
    c.post("/api/recording", json={"action": "stop"})
    rig.run(300)


def test_session_history_and_csv_A6(rig: Rig) -> None:
    _one_recording(rig, guests=2)
    rig.client.delete("/api/session")
    rig.run(60)
    rows = rig.client.get("/api/sessions").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["username"] == "testa"
    assert row["participants"] == 3
    assert row["started_by"] == "tech"  # the test client is admin in the simulator
    assert row["duration_s"] >= 6
    assert row["ended_at"] is not None
    text = rig.client.get("/api/sessions.csv").text
    assert text.startswith("﻿started_at;ended_at;username")
    assert "testa" in text
    log = rig.client.get("/api/log.csv")
    assert log.headers["content-type"].startswith("text/csv")
    assert "attachment" in log.headers["content-disposition"]
    assert ";cut;" in log.text


def test_session_history_survives_restart(tmp_path: Path) -> None:
    first = Rig(tmp_path)
    _one_recording(first)
    first.store.close()
    second = Rig(tmp_path)
    try:
        rows = second.client.get("/api/sessions").json()
        assert [r["username"] for r in rows] == ["testa"]
    finally:
        second.store.close()


def test_debug_package_has_log_config_version_and_no_secrets_A6(rig: Rig) -> None:
    import io
    import zipfile

    _one_recording(rig)
    r = rig.client.get("/api/debug-package")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(z.namelist())
    for must in ("README.txt", "version.json", "state.json", "rules.json", "decisions.jsonl"):
        assert f"cutcut-feilsok/{must}" in names
    assert any(n.startswith("cutcut-feilsok/site/shows/") for n in names)
    assert not any("staff" in n for n in names)
    blob = b"".join(z.read(n) for n in names).decode("utf-8")
    assert TEST_CARD not in blob  # I8
    assert SIM_PIN not in blob.replace('"1234', "")  # no PIN, even as a substring of values
    assert "operator_pin" not in blob
    assert "admin_pin" not in blob


def test_exports_need_the_right_role(tmp_path: Path) -> None:
    rig = Rig(tmp_path, dev_admin=False)
    try:
        assert rig.client.get("/api/sessions").status_code == 403
        assert rig.client.get("/api/debug-package").status_code == 403
    finally:
        rig.store.close()
