"""Find the 2 + 8 windows in a picture of the multiview (setup step 6, VI-5).

The ATEM draws thin lines between the windows. Across a whole row or column of the picture
they give a sharp step in brightness that camera pictures do not, so the sum of the brightness
steps per column (and per row) peaks where a window edge is. We look for each expected edge
near where the 2 + 8 layout puts it inside the part of the picture that is not black (the
capture can have black bars), and keep the peak.

The result is a suggestion: the technician sees it drawn on the picture and can drag the
corners before saving. Only numpy, so it runs in ``core`` on the newest thumbnail.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Rect = tuple[float, float, float, float]

BLACK = 12.0  # mean brightness of a row/column that is black bar, not picture
SEARCH = 0.03  # look this far (share of the picture) on each side of the expected edge
STRONG = 3.0  # an edge must be this many times the typical step to count as found


@dataclass(frozen=True)
class Grid:
    """Window rectangles (share of the picture), and how sure we are."""

    big: tuple[Rect, Rect]  # left, right
    small: tuple[Rect, ...]  # 8 windows, row by row, left to right
    found: bool  # every edge was clearly seen; otherwise the standard grid in the picture
    bounds: Rect  # the part of the picture that is not black
    strength: float  # weakest edge, in multiples of the typical step


def _bounds(gray: NDArray[np.float32]) -> tuple[int, int, int, int] | None:
    rows = np.flatnonzero(gray.mean(axis=1) > BLACK)
    cols = np.flatnonzero(gray.mean(axis=0) > BLACK)
    if rows.size == 0 or cols.size == 0:
        return None
    return int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1


def _peak(profile: NDArray[np.float32], want: float, lo: int, hi: int) -> tuple[int, float]:
    """Index of the strongest step within ``SEARCH`` of ``want``, and its strength."""
    span = hi - lo
    a = max(lo + 1, round(want - SEARCH * span))
    b = min(hi - 1, round(want + SEARCH * span) + 1)
    typical = float(np.median(profile[lo:hi])) + 1e-3
    if b <= a:
        return round(want), 0.0
    i = a + int(np.argmax(profile[a:b]))
    return i, float(profile[i]) / typical


def find_grid(frame: NDArray[np.uint8]) -> Grid | None:
    """``None`` for a black picture (no signal)."""
    gray = frame.astype(np.float32).mean(axis=2) if frame.ndim == 3 else frame.astype(np.float32)
    h, w = gray.shape
    b = _bounds(gray)
    if b is None:
        return None
    x0, y0, x1, y1 = b
    bw, bh = x1 - x0, y1 - y0
    part = gray[y0:y1, x0:x1]
    # steps between neighbouring columns / rows, averaged along the line
    col_top = np.abs(np.diff(part[: bh // 2], axis=1)).mean(axis=0)
    col_bottom = np.abs(np.diff(part[bh // 2 :], axis=1)).mean(axis=0)
    row_all = np.abs(np.diff(part, axis=0)).mean(axis=1)
    col = np.zeros(bw, dtype=np.float32)
    col[1:] = (col_top + col_bottom) / 2
    col_b = np.zeros(bw, dtype=np.float32)
    col_b[1:] = col_bottom
    row = np.zeros(bh, dtype=np.float32)
    row[1:] = row_all

    mid_x, s1 = _peak(col, bw / 2, 0, bw)
    q1_x, s2 = _peak(col_b, bw / 4, 0, bw)
    q3_x, s3 = _peak(col_b, bw * 3 / 4, 0, bw)
    mid_y, s4 = _peak(row, bh / 2, 0, bh)
    q3_y, s5 = _peak(row, bh * 3 / 4, 0, bh)
    strength = min(s1, s2, s3, s4, s5)
    found = strength >= STRONG
    if not found:  # the standard grid inside the picture
        mid_x, q1_x, q3_x = round(bw / 2), round(bw / 4), round(bw * 3 / 4)
        mid_y, q3_y = round(bh / 2), round(bh * 3 / 4)

    def r(ax: int, ay: int, bx: int, by: int) -> Rect:
        return (
            round((x0 + ax) / w, 4),
            round((y0 + ay) / h, 4),
            round((bx - ax) / w, 4),
            round((by - ay) / h, 4),
        )

    xs = [0, q1_x, mid_x, q3_x, bw]
    ys = [mid_y, q3_y, bh]
    small = tuple(r(xs[c], ys[rw], xs[c + 1], ys[rw + 1]) for rw in range(2) for c in range(4))
    return Grid(
        big=(r(0, 0, mid_x, mid_y), r(mid_x, 0, bw, mid_y)),
        small=small,
        found=found,
        bounds=(round(x0 / w, 4), round(y0 / h, 4), round(bw / w, 4), round(bh / h, 4)),
        strength=round(strength, 1),
    )


def program_side(frame: NDArray[np.uint8], grid: Grid) -> str | None:
    """«left» or «right»: the big window with the red tally frame (program). ``None`` when
    neither frame is clearly red (tally off, or a capture that loses colour)."""
    if frame.ndim != 3:
        return None
    h, w = frame.shape[:2]

    def redness(rect: Rect) -> float:
        x, y, rw, rh = rect
        a, b = round(y * h), round((y + rh) * h)
        c, d = round(x * w), round((x + rw) * w)
        edge = 3
        strips = [
            frame[a : a + edge, c:d],
            frame[b - edge : b, c:d],
            frame[a:b, c : c + edge],
            frame[a:b, d - edge : d],
        ]
        px = np.concatenate([s.reshape(-1, 3) for s in strips if s.size]).astype(np.float32)
        if px.size == 0:
            return 0.0
        # frames are BGR (OpenCV); red is channel 2
        return float((px[:, 2] - px[:, :2].max(axis=1)).mean())

    left, right = redness(grid.big[0]), redness(grid.big[1])
    if max(left, right) < 40 or abs(left - right) < 30:
        return None
    return "left" if left > right else "right"
