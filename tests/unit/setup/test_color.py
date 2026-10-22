"""P8 (F-10, spec 6.4): the grey card is found in each camera window, and the cameras are
brought to the reference in a few rounds; a camera on air is skipped."""

from __future__ import annotations

import asyncio
import math

import numpy as np

from cutcut.common.ids import CameraId
from cutcut.setup.color import CameraColor, ColorMatcher, find_grey

C1, C2, C3 = CameraId.C1, CameraId.C2, CameraId.C3


def scene(card_bgr: tuple[float, float, float], seed: int = 1) -> np.ndarray:
    """A busy picture (a person, a wall) with a grey card in the middle."""
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 255, (270, 480, 3)).astype(np.float32)
    img[60:210, 160:320] = card_bgr
    img[60:210, 160:320] += rng.normal(0, 1.5, (150, 160, 3))
    return np.clip(img, 0, 255).astype(np.uint8)


def test_the_grey_card_is_found_and_measured() -> None:
    p = find_grey(scene((120, 128, 140)))  # BGR: a little warm
    assert p is not None
    assert abs(p.b - 120) < 3
    assert abs(p.r - 140) < 3
    assert p.share > 0.1


def test_no_card_no_patch() -> None:
    rng = np.random.default_rng(2)
    assert find_grey(rng.integers(0, 255, (270, 480, 3), dtype=np.uint8)) is None
    red = np.zeros((270, 480, 3), dtype=np.uint8)
    red[:, :, 2] = 200  # even, but not grey
    assert find_grey(red) is None


class Studio:
    """Cameras whose picture of the card depends on their white balance and gain, like a
    real camera: a higher kelvin setting makes the picture warmer; gain makes it brighter."""

    def __init__(self) -> None:
        self.true = {C1: (1.0, 128.0), C2: (1.2, 100.0), C3: (0.85, 150.0)}  # r/b, luma at 0 dB
        self.set = {c: (5600, 0.0) for c in self.true}
        self.on_air: set[CameraId] = set()

    def grab(self, cam: CameraId) -> np.ndarray:
        rb, luma = self.true[cam]
        kelvin, gain = self.set[cam]
        rb *= math.exp((kelvin - 5600) / 3000)
        luma *= 10 ** (gain / 20)
        r, b = luma * math.sqrt(rb), luma / math.sqrt(rb)
        return scene((b, luma, r))

    def apply(self, cam: CameraId, kelvin: int, gain: float) -> str:
        if cam in self.on_air:
            return "on_program"
        self.set[cam] = (kelvin, gain)
        return "queued"


async def no_wait(_: float) -> None:
    return None


def run(studio: Studio) -> ColorMatcher:
    m = ColorMatcher(
        C1,
        {C2: CameraColor(), C3: CameraColor()},
        studio.grab,
        studio.apply,
        sleep=no_wait,
    )
    asyncio.run(m.run())
    return m


def test_the_cameras_are_brought_to_the_reference() -> None:
    s = Studio()
    m = run(s)
    assert m.state == "ferdig"
    assert m.cameras[C2].state == "ferdig"
    assert m.cameras[C3].state == "ferdig"
    assert m.cameras[C2].kelvin < 5600  # C2 was warm
    assert m.cameras[C3].kelvin > 5600  # C3 was cold
    assert m.cameras[C2].gain_db > 0  # and dark
    assert m.round <= 5


def test_a_camera_on_air_is_never_adjusted() -> None:
    s = Studio()
    s.on_air.add(C2)
    m = run(s)
    assert m.cameras[C2].state == "hoppet over"
    assert s.set[C2] == (5600, 0.0)
    assert m.cameras[C3].state == "ferdig"


def test_no_card_at_the_reference_stops_with_a_reason() -> None:
    s = Studio()
    rng = np.random.default_rng(3)
    m = ColorMatcher(
        C1,
        {C2: CameraColor()},
        lambda cam: (
            rng.integers(0, 255, (270, 480, 3), dtype=np.uint8) if cam is C1 else s.grab(cam)
        ),
        s.apply,
        sleep=no_wait,
    )
    asyncio.run(m.run())
    assert m.state == "feil"
    assert "referansekameraet C1" in (m.message or "")


def test_the_setup_page_needs_the_video_layer_and_the_cameras(tmp_path: object) -> None:
    from pathlib import Path

    from tests.unit.devices.test_tracking import CamRig

    rig = CamRig(Path(str(tmp_path)))
    try:
        st = rig.client.get("/api/setup/color").json()
        assert st["cameras"] == ["C1", "C2", "C3", "C4"]
        assert st["run"] is None
        r = rig.client.post("/api/setup/color", json={"reference": "C1"})
        assert r.status_code == 409
        assert "Videolaget kjører ikke" in r.json()["detail"]
    finally:
        rig.store.close()
