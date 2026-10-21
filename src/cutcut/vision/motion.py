"""Camera movement and program confirmation from the multiview (VI-3).

* **Movement (``S1``, ``V5``):** a camera that pans, tilts or zooms changes almost its whole
  picture from one frame to the next; a person who gestures changes a small part. A camera tile
  with over 35 % of its pixels changed in two frames in a row counts as moving, and stays so
  until it has been still for 0.5 s (``V5``). The engine never cuts to it meanwhile (``S1``).
  The camera drivers (CA-2) add what the cameras themselves report.
* **Program confirmation:** the program window is compared with every camera window (small
  grey copies, normalised): the closest one, if clearly closer than the next, is what is on air.
  Core compares that with what the ATEM says.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

import numpy as np
import numpy.typing as npt

from cutcut.vision.tiles import Frame

MOVING_SHARE: Final = 0.35
MOVING_FRAMES: Final = 2
STILL_MS: Final = 500  # V5
THUMB: Final = (18, 32)  # rows, columns: enough to tell cameras apart
MATCH_MAX: Final = 0.35  # mean absolute difference of normalised thumbs
MATCH_MARGIN: Final = 0.08

Thumb = npt.NDArray[np.float32]


@dataclass
class MotionTracker:
    """Per camera: moving now, or within the last 0.5 s."""

    _streak: dict[str, int] = field(default_factory=dict)
    _last_move: dict[str, int] = field(default_factory=dict)

    def feed(self, now: int, changes: dict[str, float]) -> list[str]:
        for cam, change in changes.items():
            streak = self._streak.get(cam, 0) + 1 if change >= MOVING_SHARE else 0
            self._streak[cam] = streak
            if streak >= MOVING_FRAMES:
                self._last_move[cam] = now
        return sorted(c for c, t in self._last_move.items() if now - t <= STILL_MS)


def thumb(area: Frame) -> Thumb:
    """A small, normalised grey copy (mean 0, spread 1), by index sampling: no OpenCV needed."""
    h, w = area.shape[:2]
    rows = np.linspace(0, h - 1, THUMB[0]).astype(int)
    cols = np.linspace(0, w - 1, THUMB[1]).astype(int)
    small = area[np.ix_(rows, cols)]
    gray = np.asarray(small.mean(axis=2) if small.ndim == 3 else small, dtype=np.float32)
    std = float(gray.std())
    out: Thumb = ((gray - gray.mean()) / (std if std > 1.0 else 1.0)).astype(np.float32)
    return out


def match_program(pgm: Thumb, cameras: dict[str, Thumb]) -> tuple[str | None, float]:
    """Which camera is on program (or None if none is clearly closest), and how close."""
    if not cameras:
        return None, 1.0
    scores = sorted((float(np.abs(pgm - t).mean()) / 2.0, cam) for cam, t in cameras.items())
    best, cam = scores[0]
    second = scores[1][0] if len(scores) > 1 else 1.0
    if best <= MATCH_MAX and second - best >= MATCH_MARGIN:
        return cam, round(best, 3)
    return None, round(best, 3)
