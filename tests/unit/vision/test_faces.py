"""P6: faces, mouth, smile and nod per camera window (spec 6.6), from YuNet's box and five
points. The numbers are tested on drawn pictures with known changes; the real model is only
loaded and timed here (accuracy is measured on studio footage)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from cutcut.core import messages
from cutcut.vision.capture import SyntheticSource
from cutcut.vision.faces import MODEL, FaceAnalyzer, FaceReading, FaceTracker, load
from cutcut.vision.process import run
from tests.unit.vision.test_vision import MV

H, W = 270, 480
MODELS = Path(__file__).resolve().parents[3] / "models"


def picture(seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(60, 120, (H, W, 3), dtype=np.uint8)


def face(
    x: float = 180,
    y: float = 60,
    w: float = 120,
    h: float = 150,
    eyes_y: float = 110,
    mouth_w: float = 40,
) -> np.ndarray:
    cx = x + w / 2
    row = [
        x, y, w, h,
        cx - 30, eyes_y, cx + 30, eyes_y,  # eyes (right, left as YuNet)
        cx, eyes_y + 30,  # nose
        cx - mouth_w / 2, eyes_y + 65, cx + mouth_w / 2, eyes_y + 65,  # mouth corners
        0.95,
    ]  # fmt: skip
    return np.array([row], dtype=np.float32)


def test_no_face_is_not_ok() -> None:
    r = FaceTracker().update(0.0, picture(), None)
    assert r == FaceReading()


def test_face_size_and_position_for_V2() -> None:
    assert FaceTracker().update(0, picture(), face()).size_ok is True
    assert FaceTracker().update(0, picture(), face(w=20, h=25)).size_ok is False  # too small
    assert FaceTracker().update(0, picture(), face(x=400, w=90)).size_ok is False  # cut off


def test_mouth_moves_while_the_face_stands_still() -> None:
    t = FaceTracker()
    img = picture()
    t.update(0.0, img, face())
    still = t.update(0.2, img.copy(), face())
    assert still.mouth < 0.05
    talking = img.copy()
    talking[165:185, 220:260] = 240  # the mouth opens
    r = t.update(0.4, talking, face())
    assert r.mouth > 0.5


def test_a_head_that_moves_is_not_a_mouth_that_talks() -> None:
    t = FaceTracker()
    t.update(0.0, picture(1), face())
    moved = picture(2)  # everything in the face changes, mouth included
    r = t.update(0.2, moved, face())
    assert r.mouth < 0.3


def test_smile_is_wider_than_this_persons_usual() -> None:
    t = FaceTracker()
    for i in range(8):
        t.update(i * 0.2, picture(), face(mouth_w=40))
    assert t.update(2.0, picture(), face(mouth_w=40)).smile == 0
    assert t.update(2.2, picture(), face(mouth_w=47)).smile > 0.9


def test_a_nod_goes_down_and_up_again() -> None:
    t = FaceTracker()
    ys = [110, 112, 116, 120, 116, 111]  # eyes down 10 px of a 150 px face, and back
    out = [t.update(i * 0.2, picture(), face(eyes_y=y)).nod for i, y in enumerate(ys)]
    assert out[-1] > 0.3
    still = FaceTracker()
    flat = [still.update(i * 0.2, picture(), face(eyes_y=110)).nod for i in range(6)]
    assert max(flat) == 0


def test_the_analyzer_keeps_going_when_one_window_fails() -> None:
    calls: list[int] = []

    def detect(img: np.ndarray) -> np.ndarray | None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return face()

    a = FaceAnalyzer(detect)
    out = a.analyze(0.0, {"C1": picture(), "C2": picture()})
    assert out["C1"].found is False
    assert out["C2"].found is True
    assert a.last_ms is not None


def test_the_engine_gets_the_numbers() -> None:
    reading = FaceReading(True, True, 0.8, 0.1, 0.6)
    source, tile = messages.tile(reading.payload("C2"))
    assert source.value == "C2"
    assert tile.face_ok is True
    assert tile.mouth == pytest.approx(0.8)
    assert tile.nod == pytest.approx(0.6)


def test_the_video_layer_publishes_faces_per_camera() -> None:
    sent: list[tuple[str, dict[str, Any]]] = []

    async def publish(topic: str, payload: dict[str, Any]) -> None:
        sent.append((topic, payload))

    analyzer = FaceAnalyzer(lambda img: face())
    asyncio.run(run(SyntheticSource(MV), MV, publish, max_frames=3, realtime=False, faces=analyzer))
    tiles = [p for t, p in sent if t == "vision.tile"]
    assert {p["source"] for p in tiles} >= {"C1", "C2"}
    assert "LAPTOP" not in {p["source"] for p in tiles}
    status = next(p for t, p in sent if t == "vision.status")
    assert status["faces"] is True


@pytest.mark.skipif(not (MODELS / MODEL).is_file(), reason="model not fetched")
def test_yunet_loads_and_finds_nothing_in_an_empty_picture() -> None:
    pytest.importorskip("cv2")
    analyzer = load(MODELS)
    assert analyzer is not None
    out = analyzer.analyze(0.0, {"C1": np.zeros((H, W, 3), dtype=np.uint8)})
    assert out["C1"].found is False
    assert analyzer.last_ms is not None
    assert analyzer.last_ms < 500  # a window in well under half a second, even in CI


def test_without_the_model_the_light_layer_runs_alone(tmp_path: Path) -> None:
    assert load(tmp_path) is None


def test_the_footage_report() -> None:
    from cutcut.hwtest.faces import measure
    from cutcut.vision.process import Vision

    def scaled(img: np.ndarray) -> np.ndarray:
        f = face()
        f[0, :14] *= img.shape[1] / W  # the drawn windows are smaller than 480 × 270
        return f

    report = measure(Vision(MV), SyntheticSource(MV), FaceAnalyzer(scaled), rounds=5)
    ids = [s.id for s in report.steps]
    assert ids == ["F1", "F2", "F3"]
    assert report.steps[0].result == "ok"
