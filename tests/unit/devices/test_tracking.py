"""AI-tracking AT1–AT6 (spec 5.12, P5) and the camera controls on the Kameraer page.

The simulator runs with fake PTZ cameras behind the real camera guard, so the same rules hold
as in the studio: nothing moves a camera on program or preview (I2), and a tracking camera is
left alone (AT3)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cutcut.api.app import create_app
from cutcut.common.clock import FakeClock
from cutcut.common.ids import CameraId, SourceId
from cutcut.common.store import Store
from cutcut.core.intents import FrameCamera
from cutcut.core.runtime import TICK_MS
from cutcut.devices.cameras.base import PTZPosition
from cutcut.devices.cameras.service import CameraService
from cutcut.sim.live import build_live_sim, sim_routes
from tests.rules.harness import started
from tests.unit.api.test_api import TEST_CARD

C2 = CameraId.C2


class CamRig:
    def __init__(self, tmp: Path) -> None:
        self.clock = FakeClock()
        self.store = Store(tmp / "cutcut.db")
        self.sim, auth = build_live_sim(self.clock, store=self.store, cameras=True)
        app = create_app(self.sim.studio, auth, run_loop=False, extra_routes=sim_routes(self.sim))
        self.client = TestClient(app)
        cams = self.sim.studio.deps.cameras
        assert cams is not None
        self.cams: CameraService = cams

    def run(self, ms: int) -> None:
        for _ in range(ms // TICK_MS):
            self.clock.advance(TICK_MS)
            self.sim.before_tick()
            self.sim.studio.tick()

    def drain(self) -> None:
        async def go() -> None:
            for g in self.cams.guards.values():
                while await g.step():
                    pass

        asyncio.run(go())

    def switch(self, mode: str) -> None:
        r = self.client.post("/api/features", json={"ai_tracking": mode})
        assert r.status_code == 200, r.text


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[CamRig]:
    r = CamRig(tmp_path)
    r.run(100)
    yield r
    r.store.close()


def test_the_kameraer_page_lists_the_steered_cameras(rig: CamRig) -> None:
    cams = {c["id"]: c for c in rig.client.get("/api/cameras").json()}
    assert set(cams) == {"C1", "C2", "C3", "C4"}
    assert cams["C2"]["can_track"] is True  # OBSBOT
    assert cams["C1"]["can_track"] is False  # Canon
    assert cams["C2"]["presets"] == {"tight": 1, "wide": 2}


def test_presets_and_steps_are_refused_on_air(rig: CamRig) -> None:
    c = rig.client
    rig.sim.atem.program = rig.sim.atem.preview = SourceId.C2  # C2 on air
    r = c.post("/api/cameras/C2/preset", json={"n": 2})
    assert r.status_code == 409
    assert "program" in r.json()["detail"]
    assert c.post("/api/cameras/C3/preset", json={"n": 2}).status_code == 200
    assert c.post("/api/cameras/C3/nudge", json={"pan": 0.2}).status_code == 200
    assert c.post("/api/cameras/C9/nudge", json={"pan": 0.2}).status_code == 404


def test_AT1_needs_the_switch_and_only_obsbot(rig: CamRig) -> None:
    c = rig.client
    r = c.post("/api/cameras/C2/tracking", json={"on": True})
    assert r.status_code == 409
    assert "Regi → Brytere" in r.json()["detail"]
    rig.switch("on")
    r = c.post("/api/cameras/C1/tracking", json={"on": True})
    assert r.status_code == 409
    assert "OBSBOT" in r.json()["detail"]
    assert c.post("/api/cameras/C2/tracking", json={"on": True}).status_code == 200
    rig.drain()
    assert rig.cams.guards[C2].st.tracking is True


def test_AT1_in_shadow_only_logs(rig: CamRig) -> None:
    rig.switch("shadow")
    assert rig.client.post("/api/cameras/C2/tracking", json={"on": True}).status_code == 200
    rig.drain()
    assert rig.cams.guards[C2].st.tracking is False
    assert any(a["code"] == "AT1" for a in rig.sim.studio.state().model_dump()["alerts"])


def test_AT3_a_tracking_camera_is_left_alone(rig: CamRig) -> None:
    rig.switch("on")
    rig.client.post("/api/cameras/C2/tracking", json={"on": True})
    rig.drain()
    r = rig.client.post("/api/cameras/C2/preset", json={"n": 1})
    assert r.status_code == 409
    assert "AT3" in r.json()["detail"]
    rig.run(60)
    assert C2 in rig.sim.studio.runtime._inputs(0).cameras_tracking


def test_AT3_the_engine_does_not_reframe_a_tracking_camera() -> None:
    h = started(features={"framing_variety": True})
    h.tracking.add(CameraId.C1)
    for i in range(6):
        h.stop_all()
        h.talk(("P1", "P2")[i % 2])
        h.run(5000)
    assert not [i for _, i in h.intents if isinstance(i, FrameCamera) and i.camera is CameraId.C1]


def test_AT4_calm_tracking_is_not_moving_but_a_fast_swing_is(rig: CamRig) -> None:
    g = rig.cams.guards[C2]
    g.st.tracking = True
    fake = g.driver
    clock = {"t": 100.0}
    g.clock = rig.cams.clock = lambda: clock["t"]

    async def poll(pan: float) -> bool:
        fake.pan = pan  # type: ignore[attr-defined]
        clock["t"] += 2.0
        return await rig.cams._poll_one(C2, g)

    async def go() -> tuple[bool, bool]:
        await g.refresh()
        calm = await poll(fake.pan + 4.0)  # type: ignore[attr-defined]  # 2°/s
        fast = await poll(fake.pan + 20.0)  # type: ignore[attr-defined]  # 10°/s
        return calm, fast

    calm, fast = asyncio.run(go())
    assert calm is False
    assert fast is True
    assert isinstance(g.st.position, PTZPosition)


def test_AT5_off_is_allowed_even_on_air(rig: CamRig) -> None:
    rig.switch("on")
    rig.client.post("/api/cameras/C2/tracking", json={"on": True})
    rig.drain()
    rig.sim.atem.program = SourceId.C2
    assert rig.client.post("/api/cameras/C2/tracking", json={"on": False}).status_code == 200
    rig.drain()
    assert rig.cams.guards[C2].st.tracking is False


def test_AT6_tracking_goes_off_when_the_session_ends(rig: CamRig) -> None:
    c = rig.client
    rig.switch("on")
    c.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(100)
    c.post("/api/cameras/C2/tracking", json={"on": True})
    rig.drain()
    assert rig.cams.guards[C2].st.tracking is True
    c.post("/api/logout")
    c.post("/api/session/end")
    rig.sim.studio.sessions.session = None
    rig.run(100)
    rig.drain()
    assert rig.cams.guards[C2].st.tracking is False
