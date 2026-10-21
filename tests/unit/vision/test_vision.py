"""VI-1: tiles from the rutekart, from a drawn multiview and from a real video file."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from cutcut.common.config import load_site
from cutcut.common.models.multiview import MultiviewMap
from cutcut.vision.capture import OpenCvSource, SyntheticSource
from cutcut.vision.process import Vision, run
from cutcut.vision.tiles import INSET, cuts

ROOT = Path(__file__).resolve().parents[3]


def _map() -> MultiviewMap:
    mv = load_site(ROOT / "site" / "ntnu-studio").multiview
    assert mv is not None
    return mv


MV = _map()


def test_tiles_are_cut_four_percent_in() -> None:
    by_id = {c.tile.id: c for c in cuts(MV, 1080, 1920)}
    w1 = by_id["W1"]  # x 0–0.25, y 0.5–0.75
    assert (w1.x0, w1.x1) == (round(0.25 * INSET * 1920), round((0.25 - 0.25 * INSET) * 1920))
    assert (w1.y0, w1.y1) == (
        round((0.5 + 0.25 * INSET) * 1080),
        round((0.75 - 0.25 * INSET) * 1080),
    )
    assert by_id["PGM"].x0 == round((0.5 + 0.5 * INSET) * 1920)
    assert len(by_id) == 10


def test_the_tally_border_is_cut_away() -> None:
    src = SyntheticSource(MV)
    frame = src.read()
    assert frame is not None
    for c in cuts(MV, *frame.shape[:2]):
        area = c.of(frame)
        assert area.min() > 0 or (c.tile.camera is not None and c.tile.camera.value == "LAPTOP")


def test_signal_change_and_sources() -> None:
    src = SyntheticSource(MV, content="none")
    v = Vision(MV)
    first = {r["tile"]: r for r in v.measure(src.read())}  # type: ignore[arg-type]
    assert first["W1"]["source"] == "C1"
    assert first["W1"]["signal"] is True
    assert first["W6"]["signal"] is False  # laptop not connected: black
    assert "source" not in first["W7"]  # media player: no CutCut camera
    src.moving.add("W2")
    v.measure(src.read())  # type: ignore[arg-type]
    rows = {r["tile"]: r for r in v.measure(src.read())}  # type: ignore[arg-type]
    assert rows["W2"]["change"] > 0.01
    assert rows["W3"]["change"] == 0.0
    src.content = "video"
    v.measure(src.read())  # type: ignore[arg-type]
    rows = {r["tile"]: r for r in v.measure(src.read())}  # type: ignore[arg-type]
    assert rows["W6"]["signal"] is True
    assert rows["W6"]["change"] > 0.5


def test_the_loop_publishes_frames_and_status() -> None:
    sent: list[tuple[str, dict[str, Any]]] = []

    async def publish(topic: str, payload: dict[str, Any]) -> None:
        sent.append((topic, payload))

    n = asyncio.run(run(SyntheticSource(MV), MV, publish, max_frames=20, realtime=False))
    assert n == 20
    assert sent[0][0] == "vision.status"
    frames = [p for t, p in sent if t == "vision.frame"]
    assert len(frames) == 20
    assert len(frames[0]["tiles"]) == 10
    status = next(p for t, p in sent if t == "vision.status")
    assert status["source"] == "syntetisk"


def test_frames_from_a_video_file(tmp_path: Path) -> None:
    """«Ruter publiseres fra fil»: a real file through OpenCV, looping."""
    cv2 = pytest.importorskip("cv2")
    path = tmp_path / "multiview.avi"
    src = SyntheticSource(MV, width=640, height=360)
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 15, (640, 360))
    for _ in range(10):
        out.write(src.read())
    out.release()
    sent: list[tuple[str, dict[str, Any]]] = []

    async def publish(topic: str, payload: dict[str, Any]) -> None:
        sent.append((topic, payload))

    n = asyncio.run(run(OpenCvSource(str(path)), MV, publish, max_frames=25, realtime=False))
    assert n == 25  # more than the file has: it loops
    frames = [p for t, p in sent if t == "vision.frame"]
    w1 = next(r for r in frames[0]["tiles"] if r["tile"] == "W1")
    assert w1["signal"] is True
    assert sent[0][1]["source"].startswith("fil ")


def test_a_device_that_is_missing_is_retried() -> None:
    class Cap:
        def isOpened(self) -> bool:
            return False

        def release(self) -> None:
            return None

        def set(self, *a: Any) -> bool:
            return True

    class FakeCv2:
        CAP_DSHOW = CAP_ANY = CAP_PROP_FRAME_WIDTH = CAP_PROP_FRAME_HEIGHT = CAP_PROP_FPS = 0
        opened = 0

        def VideoCapture(self, *a: Any) -> Cap:
            FakeCv2.opened += 1
            return Cap()

    t = [0.0]
    src = OpenCvSource(0, clock=lambda: t[0], cv2=FakeCv2())
    assert src.read() is None
    assert src.last_error == "kan ikke åpne enhet 0"
    src.read()
    assert FakeCv2.opened == 1  # waits 5 s
    t[0] = 6.0
    src.read()
    assert FakeCv2.opened == 2


def test_light_measurement_is_cheap() -> None:
    import time

    big = SyntheticSource(MV, width=1920, height=1080)
    frame = big.read()
    assert frame is not None
    v = Vision(MV)
    v.measure(frame)
    t0 = time.perf_counter()
    for _ in range(15):
        v.measure(frame)
    per_frame_ms = (time.perf_counter() - t0) * 1000 / 15
    assert per_frame_ms < 15  # 15 Hz needs < 66 ms; plan: under 25 % of one core
    assert np.isfinite(per_frame_ms)
