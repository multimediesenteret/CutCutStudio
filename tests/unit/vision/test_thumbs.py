"""D-056: camera cut-outs in the technician window, only while someone looks."""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cutcut.api.app import create_app
from cutcut.common.clock import FakeClock
from cutcut.common.store import Store
from cutcut.core.runtime import TICK_MS
from cutcut.sim.live import LiveSim, build_live_sim, sim_routes
from cutcut.vision.capture import SyntheticSource
from cutcut.vision.process import Vision, run
from tests.unit.vision.test_vision import MV

pytest.importorskip("cv2")

JPEG = b"\xff\xd8"


def test_thumbnails_are_jpegs_of_cameras_laptop_preview_and_program() -> None:
    frame = SyntheticSource(MV).read()
    assert frame is not None
    v = Vision(MV)
    v.measure(frame)  # learns the frame size and cuts the windows
    got = v.thumbnails(frame)
    assert {"C1", "C2", "C3", "C4", "C5", "LAPTOP", "PVW", "PGM"} <= set(got)
    for data in got.values():
        assert base64.b64decode(data).startswith(JPEG)


@pytest.mark.parametrize("wanted", [False, True])
def test_thumbs_are_sent_only_while_wanted(wanted: bool) -> None:
    sent: list[str] = []

    async def publish(topic: str, payload: dict[str, Any]) -> None:
        sent.append(topic)

    asyncio.run(
        run(
            SyntheticSource(MV),
            MV,
            publish,
            max_frames=5,
            realtime=False,
            want_thumbs=lambda: wanted,
        )
    )
    assert ("vision.thumbs" in sent) is wanted


class Rig:
    def __init__(self, tmp: Path) -> None:
        self.clock = FakeClock()
        self.store = Store(tmp / "cutcut.db")
        self.sim: LiveSim
        self.sim, auth = build_live_sim(self.clock, store=self.store, vision=True)
        app = create_app(self.sim.studio, auth, run_loop=False, extra_routes=sim_routes(self.sim))
        self.client = TestClient(app)

    def run(self, ms: int) -> None:
        for _ in range(ms // TICK_MS):
            self.clock.advance(TICK_MS)
            self.sim.before_tick()
            self.sim.studio.tick()


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def test_the_window_asks_and_gets_pictures_then_they_stop(rig: Rig) -> None:
    c = rig.client
    rig.run(1000)
    assert c.get("/api/state").json()["runtime"]["vision"] is True  # the drawn video layer runs
    assert c.get("/api/vision/thumb/C1").status_code == 404  # nobody asked yet: none sent
    rig.run(1000)
    r = c.get("/api/vision/thumb/C1")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content.startswith(JPEG)
    assert c.get("/api/vision/thumb/PGM").status_code == 200
    assert c.get("/api/vision/thumb/NOPE").status_code == 404
    rig.run(15_000)  # the window was closed: no more pictures, the old ones go stale
    assert c.get("/api/vision/thumb/C1").status_code == 404


def test_no_video_layer_no_pictures(tmp_path: Path) -> None:
    from tests.unit.api.test_api import Rig as Plain

    rig = Plain(tmp_path)
    try:
        rig.run(2000)
        assert rig.state()["runtime"]["vision"] is False
        assert rig.client.get("/api/vision/thumb/C1").status_code == 404
    finally:
        rig.store.close()
