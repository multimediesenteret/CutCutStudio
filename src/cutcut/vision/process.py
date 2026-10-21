"""The vision loop (VI-1): source → tiles → measurements on the bus.

Frames are taken at 15 Hz. For each tile the light part measures what the later deliveries
build on: is there a picture (``signal``), how bright, and how much changed since the last
frame (``change``, VI-2 and VI-3 turn that into content and movement). Published:

* ``vision.frame`` with every tile, 15 Hz. (``vision.tile`` with face and mouth, which the
  engine's ``video_confirm`` reads, comes with the heavy part in M4.)
* ``vision.content`` from the laptop tile (VI-2, :mod:`cutcut.vision.content`), 5 Hz and at
  once when the state changes;
* ``vision.status`` once a second: fps, frame size, source, last error (``H-VID-1``).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Final

import numpy as np

from cutcut.common.models.multiview import MultiviewMap
from cutcut.vision.capture import Source
from cutcut.vision.content import ContentDetector
from cutcut.vision.tiles import Cut, Frame, cuts

log = logging.getLogger(__name__)

FPS: Final = 15.0
SIGNAL_LEVEL: Final = 10.0  # mean of 0–255 below this: black, no signal
CHANGE_DIFF: Final = 25  # a pixel changed if it moved this much (0–255)
SAMPLE: Final = 4  # measure every 4th pixel each way: 16× less work, same answer

Publish = Callable[[str, dict[str, Any]], Awaitable[object]]


class TileMeter:
    """Light measurements for one tile, frame to frame."""

    def __init__(self, cut: Cut) -> None:
        self.cut = cut
        self._prev: np.ndarray | None = None

    def measure(self, frame: Frame) -> dict[str, Any]:
        area = self.cut.of(frame)[::SAMPLE, ::SAMPLE]
        gray = area.mean(axis=2) if area.ndim == 3 else area.astype(np.float32)
        level = float(gray.mean())
        change = 0.0
        if self._prev is not None and self._prev.shape == gray.shape:
            change = float((np.abs(gray - self._prev) > CHANGE_DIFF).mean())
        self._prev = gray
        return {
            "tile": self.cut.tile.id,
            "level": round(level, 1),
            "signal": level >= SIGNAL_LEVEL or float(gray.std()) > 4.0,
            "change": round(change, 4),
        }


class Vision:
    def __init__(self, mv: MultiviewMap) -> None:
        self.mv = mv
        self.meters: list[TileMeter] = []
        self._shape: tuple[int, int] | None = None
        self.content = ContentDetector()
        self.laptop = next(
            (t.id for t in mv.tiles if t.camera is not None and t.camera.value == "LAPTOP"), None
        )

    def content_state(self, now_ms: int, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        row = next((r for r in rows if r["tile"] == self.laptop), None)
        if row is None:
            return None
        state = self.content.feed(now_ms, bool(row["signal"]), float(row["change"]))
        return {"state": state.value, "changed_ratio": self.content.changed_ratio}

    def measure(self, frame: Frame) -> list[dict[str, Any]]:
        h, w = frame.shape[:2]
        if self._shape != (h, w):
            self._shape = (h, w)
            self.meters = [TileMeter(c) for c in cuts(self.mv, h, w)]
        out = []
        for m in self.meters:
            row = m.measure(frame)
            if m.cut.tile.camera is not None:
                row["source"] = m.cut.tile.camera.value
            out.append(row)
        return out


async def run(
    source: Source,
    mv: MultiviewMap,
    publish: Publish,
    *,
    fps: float = FPS,
    max_frames: int | None = None,
    realtime: bool = True,
    on_frame: Callable[[Frame, list[dict[str, Any]]], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """Run until ``max_frames`` (or forever). Returns the number of frames measured."""
    vision = Vision(mv)
    frames = 0
    last_content: dict[str, Any] | None = None
    last_content_at = -1.0
    last_status = -1.0
    period = 1.0 / fps
    window: list[float] = []
    size: tuple[int, int] | None = None
    while max_frames is None or frames < max_frames:
        t0 = time.monotonic()
        frame = source.read()
        if frame is not None:
            size = (frame.shape[1], frame.shape[0])
            window.append(t0)
        window = [t for t in window if t0 - t <= 1.0]
        if t0 - last_status >= 1.0:  # first, so core knows the source before the tiles
            last_status = t0
            await publish(
                "vision.status",
                {
                    "source": source.name,
                    "fps": len(window),
                    "frames": frames,
                    "size": list(size) if size else None,
                    "ok": frame is not None,
                    "last_error": getattr(source, "last_error", None),
                },
            )
        if frame is not None:
            rows = vision.measure(frame)
            await publish("vision.frame", {"tiles": rows})
            content = vision.content_state(int(clock() * 1000), rows)
            if content is not None and (content != last_content or t0 - last_content_at >= 0.2):
                await publish("vision.content", content)
                last_content, last_content_at = content, t0
            if on_frame is not None:
                on_frame(frame, rows)
            frames += 1
        if realtime:
            await asyncio.sleep(max(0.0, period - (time.monotonic() - t0)))
        elif frame is None:
            await asyncio.sleep(0)
    return frames
