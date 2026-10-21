"""VI-3: a panning camera is held back (S1, V5); the program window is recognised."""

from __future__ import annotations

from cutcut.common.clock import FakeClock
from cutcut.common.config import effective_rules, example_site_dir, load_rule_presets, load_site
from cutcut.common.ids import CameraId
from cutcut.core.engine import Engine
from cutcut.core.inputs import EngineConfig
from cutcut.core.runtime import CoreRuntime, RecordingExecutor
from cutcut.vision.capture import SyntheticSource
from cutcut.vision.motion import MotionTracker, thumb
from cutcut.vision.process import Vision
from tests.unit.vision.test_vision import MV

FRAME_MS = 1000 / 15


def film(
    src: SyntheticSource, seconds: float, t0: float = 0.0
) -> tuple[Vision, list[tuple[int, list[str]]], float]:
    v = Vision(MV)
    out = []
    t = t0
    for _ in range(round(seconds * 15)):
        t += FRAME_MS
        frame = src.read()
        assert frame is not None
        out.append((int(t), v.moving(int(t), v.measure(frame))))
    return v, out, t


def test_a_panning_camera_is_moving_and_a_gesture_is_not() -> None:
    src = SyntheticSource(MV)
    src.panning.add("W2")  # Camera 2 (gjest 1) pans
    src.moving.add("W3")  # gjest 2 waves a hand
    _, rows, _ = film(src, 1)
    assert rows[-1][1] == ["C2"]


def test_S1_still_for_half_a_second_before_it_counts_as_still_V5() -> None:
    m = MotionTracker()
    assert m.feed(0, {"C2": 0.9}) == []  # one frame is not enough
    assert m.feed(66, {"C2": 0.9}) == ["C2"]
    assert m.feed(133, {"C2": 0.0}) == ["C2"]
    assert m.feed(566, {"C2": 0.0}) == ["C2"]
    assert m.feed(600, {"C2": 0.0}) == []


def test_the_program_window_is_recognised() -> None:
    src = SyntheticSource(MV, program="W3")
    v = Vision(MV)
    frame = src.read()
    assert frame is not None
    v.measure(frame)
    got = v.program(frame)
    assert got is not None
    assert got["source"] == "C3"
    assert got["score"] < 0.1
    src.program = "W5"
    frame = src.read()
    assert frame is not None
    got = v.program(frame)
    assert got is not None
    assert got["source"] == "C5"  # fugleperspektiv
    src.program = "W7"  # media player: no camera shows that
    frame = src.read()
    assert frame is not None
    got = v.program(frame)
    assert got is not None
    assert got["source"] is None


def test_thumbs_ignore_brightness() -> None:
    import numpy as np

    a = np.full((90, 160, 3), 100, dtype=np.uint8)
    a[30:60, 50:80] = 200
    b = (a.astype(np.int16) + 30).clip(0, 255).astype(np.uint8)  # the same, brighter
    assert float(np.abs(thumb(a) - thumb(b)).mean()) < 0.01


def test_S1_core_holds_back_what_the_video_layer_sees_move() -> None:
    site = load_site(example_site_dir())
    show = site.shows["samtale"]
    eng = Engine(EngineConfig.from_show(show, effective_rules(show, load_rule_presets())), now_ms=0)
    clock = FakeClock()
    rt = CoreRuntime(eng, clock, RecordingExecutor())
    rt.feed_cameras_moving(frozenset({CameraId.C1}))  # the camera driver says C1
    rt.feed_bus("vision.moving", {"moving": ["C2"]})  # the video layer sees C2
    assert rt._inputs(clock.mono_ms()).cameras_moving == {CameraId.C1, CameraId.C2}
    clock.advance(1500)  # the video layer went quiet: its old news no longer holds C2
    assert rt._inputs(clock.mono_ms()).cameras_moving == {CameraId.C1}
