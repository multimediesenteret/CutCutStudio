"""Faces in the camera windows: is there a usable face, does the mouth move, a smile, a nod
(spec 6.6, V1–V3, R1; P6, D-067).

The face detector is YuNet (OpenCV Zoo, MIT licence, ``models/face_detection_yunet_2023mar.onnx``)
through OpenCV's ``FaceDetectorYN``. It gives a box and five points (eyes, nose tip, mouth
corners) per face, and runs a 480 × 270 window in a few milliseconds on the studio PC's CPU,
so every camera window can be analysed five times a second without the GPU. The rest is
simple and cheap, and every number below is a starting point to be tuned on studio footage:

* **Face OK (V2):** one face, inside the window with a margin, between 12 % and 75 % of the
  window height.
* **Mouth (V1):** how much the picture changes around the mouth between two analyses, minus
  how much the whole face changes (so a head that moves is not a mouth that talks), 0–1.
* **Smile (V3, R1):** the mouth corners are further apart than this person's own usual
  (median of the last analyses), relative to the eye distance, 0–1.
* **Nod (V3, R1):** the eyes go down and up again by more than 3 % of the face height within
  1.5 s, 0–1.

Nothing here decides anything: the engine uses the numbers only with ``video_confirm`` or
``reactions`` on (or in shadow).
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt

from cutcut.vision.tiles import Frame

log = logging.getLogger(__name__)

MODEL: Final = "face_detection_yunet_2023mar.onnx"
FACES_HZ: Final = 5.0
DETECT_SIZE: Final = (480, 270)  # windows are scaled to this before detection
SCORE_MIN: Final = 0.6
FACE_MIN: Final = 0.12  # V2: face height as a share of the window height
FACE_MAX: Final = 0.75
MARGIN: Final = 0.02  # V2: the face box must be this far inside the window
MOUTH_GAIN: Final = 12.0
HEAD_DISCOUNT: Final = 0.6
SMILE_SPAN: Final = 0.12  # 12 % wider than usual counts as a full smile
SMILE_HISTORY: Final = 50
NOD_WINDOW_S: Final = 1.5
NOD_MIN: Final = 0.03
NOD_FULL: Final = 0.08

Detection = npt.NDArray[np.float32]  # YuNet row: box (4), 5 points (10), score
Detector = Callable[[Frame], Detection | None]  # all faces in a picture, one row each


@dataclass(frozen=True)
class FaceReading:
    found: bool = False
    size_ok: bool = False
    mouth: float = 0.0
    smile: float = 0.0
    nod: float = 0.0

    def payload(self, source: str) -> dict[str, object]:
        """The ``vision.tile`` message (core/messages.py)."""
        return {
            "source": source,
            "face": {"found": self.found, "size_ok": self.size_ok},
            "mouth": round(self.mouth, 3),
            "smile": round(self.smile, 3),
            "nod": round(self.nod, 3),
        }


def yunet(model: Path) -> Detector:
    """OpenCV's YuNet detector. Raises when OpenCV or the model file is missing."""
    import cv2

    if not model.is_file():
        raise FileNotFoundError(f"fant ikke {model}; kjør tools/fetch_models.py")
    det = cv2.FaceDetectorYN.create(str(model), "", DETECT_SIZE, SCORE_MIN, 0.3, 20)

    def run(img: Frame) -> Detection | None:
        h, w = img.shape[:2]
        det.setInputSize((w, h))
        _, faces = det.detect(img)
        return None if faces is None else np.asarray(faces, dtype=np.float32)

    return run


def _gray(img: Frame) -> npt.NDArray[np.float32]:
    return img.astype(np.float32).mean(axis=2) if img.ndim == 3 else img.astype(np.float32)


def _crop(
    gray: npt.NDArray[np.float32], box: tuple[float, float, float, float], size: tuple[int, int]
) -> npt.NDArray[np.float32] | None:
    """A box cut out and scaled to ``size`` by plain sampling (no OpenCV needed)."""
    h, w = gray.shape
    x0, y0, x1, y1 = (round(v) for v in box)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    patch = gray[y0:y1, x0:x1]
    ys = np.linspace(0, patch.shape[0] - 1, size[1]).astype(int)
    xs = np.linspace(0, patch.shape[1] - 1, size[0]).astype(int)
    return patch[np.ix_(ys, xs)]


@dataclass
class FaceTracker:
    """One camera window over time: the numbers need the previous analyses."""

    _mouth: npt.NDArray[np.float32] | None = None
    _face: npt.NDArray[np.float32] | None = None
    _ratios: deque[float] = field(default_factory=lambda: deque(maxlen=SMILE_HISTORY))
    _eyes_y: deque[tuple[float, float]] = field(default_factory=deque)

    def reset(self) -> None:
        self._mouth = self._face = None
        self._eyes_y.clear()

    def update(self, t: float, img: Frame, faces: Detection | None) -> FaceReading:
        h, w = img.shape[:2]
        if faces is None or len(faces) == 0:
            self.reset()
            return FaceReading()
        # the face nearest the middle of the window (the person this camera is for)
        cx = faces[:, 0] + faces[:, 2] / 2
        f = faces[int(np.argmin(np.abs(cx - w / 2)))]
        x, y, fw, fh = (float(v) for v in f[:4])
        inside = (
            x >= MARGIN * w
            and y >= MARGIN * h
            and x + fw <= (1 - MARGIN) * w
            and y + fh <= (1 - MARGIN) * h
        )
        size_ok = inside and FACE_MIN <= fh / h <= FACE_MAX
        eye_r, eye_l = f[4:6], f[6:8]
        mouth_r, mouth_l = f[10:12], f[12:14]
        eye_d = float(np.hypot(*(eye_l - eye_r))) or 1.0
        mouth_d = float(np.hypot(*(mouth_l - mouth_r)))
        gray = _gray(img)

        # mouth: change around the mouth minus change of the whole face (head movement)
        mc = (mouth_r + mouth_l) / 2
        half_w, half_h = 0.7 * mouth_d + 2, 0.45 * mouth_d + 2
        mouth = _crop(
            gray, (mc[0] - half_w, mc[1] - half_h, mc[0] + half_w, mc[1] + half_h), (32, 16)
        )
        face = _crop(gray, (x, y, x + fw, y + fh), (32, 32))
        mouth_score = 0.0
        if (
            mouth is not None
            and face is not None
            and self._mouth is not None
            and self._face is not None
        ):
            dm = float(np.abs(mouth - self._mouth).mean()) / 255
            df = float(np.abs(face - self._face).mean()) / 255
            mouth_score = min(1.0, max(0.0, dm - HEAD_DISCOUNT * df) * MOUTH_GAIN)
        self._mouth, self._face = mouth, face

        # smile: mouth width against the eye distance, compared with this person's usual
        ratio = mouth_d / eye_d
        usual = float(np.median(self._ratios)) if len(self._ratios) >= 5 else ratio
        self._ratios.append(ratio)
        smile = min(1.0, max(0.0, (ratio / usual - 1) / SMILE_SPAN)) if usual > 0 else 0.0

        # nod: the eyes go down and up again (or up and down) within NOD_WINDOW_S
        ey = float((eye_r[1] + eye_l[1]) / 2) / max(fh, 1.0)
        self._eyes_y.append((t, ey))
        while self._eyes_y and t - self._eyes_y[0][0] > NOD_WINDOW_S:
            self._eyes_y.popleft()
        ys = [v for _, v in self._eyes_y]
        nod = 0.0
        if len(ys) >= 3:
            low, high = int(np.argmax(ys)), int(np.argmin(ys))
            amp = max(ys) - min(ys)
            turned = 0 < low < len(ys) - 1 or 0 < high < len(ys) - 1  # went and came back
            if turned and amp >= NOD_MIN:
                nod = min(1.0, (amp - NOD_MIN) / (NOD_FULL - NOD_MIN))
        return FaceReading(True, size_ok, mouth_score, smile, nod)


@dataclass
class FaceAnalyzer:
    """All camera windows, at most ``FACES_HZ`` times a second."""

    detect: Detector
    trackers: dict[str, FaceTracker] = field(default_factory=dict)
    last_ms: float | None = None  # how long the last round took (status, the 12.5 budget)

    def analyze(self, t: float, windows: dict[str, Frame]) -> dict[str, FaceReading]:
        t0 = time.perf_counter()
        out: dict[str, FaceReading] = {}
        for source, img in windows.items():
            tracker = self.trackers.setdefault(source, FaceTracker())
            try:
                faces = self.detect(img)
            except Exception as exc:  # one bad window must not stop the others
                log.warning("ansiktsanalyse feilet for %s: %s", source, exc)
                faces = None
            out[source] = tracker.update(t, img, faces)
        self.last_ms = round((time.perf_counter() - t0) * 1000, 1)
        return out


def load(models_dir: Path) -> FaceAnalyzer | None:
    """The analyser when OpenCV and the model are there; else ``None`` (the light video layer
    runs as before, and the switches that need faces say why they are locked)."""
    try:
        return FaceAnalyzer(yunet(models_dir / MODEL))
    except Exception as exc:
        log.info("Ansiktsanalyse er av: %s", exc)
        return None
