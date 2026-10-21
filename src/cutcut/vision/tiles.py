"""Cutting the multiview picture into tiles (spec 6.1).

Coordinates in the rutekart are shares of the picture (0–1), so the same map works at any
resolution. Each tile is cut 4 % in on every side to drop the tally border and the label.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
import numpy.typing as npt

from cutcut.common.models.multiview import MultiviewMap, Tile

INSET: Final = 0.04

Frame = npt.NDArray[np.uint8]  # height × width × 3 (BGR, as OpenCV delivers)


@dataclass(frozen=True)
class Cut:
    tile: Tile
    y0: int
    y1: int
    x0: int
    x1: int

    def of(self, frame: Frame) -> Frame:
        view: Frame = frame[self.y0 : self.y1, self.x0 : self.x1]
        return view


def cuts(mv: MultiviewMap, height: int, width: int, inset: float = INSET) -> list[Cut]:
    out = []
    for t in mv.tiles:
        x, y, w, h = t.rect
        dx, dy = w * inset, h * inset
        x0 = round((x + dx) * width)
        x1 = round((x + w - dx) * width)
        y0 = round((y + dy) * height)
        y1 = round((y + h - dy) * height)
        out.append(Cut(t, y0, max(y1, y0 + 1), x0, max(x1, x0 + 1)))
    return out
