"""Where the multiview picture comes from (VI-1).

* :class:`OpenCvSource` – the INOGENI 4KXUSB3 (a UVC camera to Windows, DirectShow) or a
  video file. Frames are taken at 15 Hz; the rest are dropped early to save CPU. A device that
  stops delivering is opened again every 5 s, forever.
* :class:`SyntheticSource` – draws a multiview from the rutekart (tests, simulator, demo):
  grey cameras, a moving square where someone moves, and the laptop tile as black (no signal),
  a still slide or video.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Protocol

import numpy as np

from cutcut.common.models.multiview import MultiviewMap
from cutcut.vision.tiles import Frame

log = logging.getLogger(__name__)

REOPEN_S: Final = 5.0
STALL_S: Final = 1.0


class Source(Protocol):
    name: str

    def read(self) -> Frame | None:
        """The newest frame, or None if there is none (yet)."""
        ...

    def close(self) -> None: ...


class OpenCvSource:
    """A capture device (index) or a file (path) through OpenCV."""

    def __init__(
        self,
        spec: int | str,
        *,
        width: int = 1920,
        height: int = 1080,
        loop: bool = True,
        clock: Callable[[], float] = time.monotonic,
        cv2: Any = None,
    ) -> None:
        self.spec = spec
        self.width, self.height = width, height
        self.loop = loop
        self.clock = clock
        self._cv2 = cv2
        self.name = f"enhet {spec}" if isinstance(spec, int) else f"fil {spec}"
        self._cap: Any = None
        self._next_open = 0.0
        self._last_frame = 0.0
        self.last_error: str | None = None
        self.opened = 0

    @property
    def is_file(self) -> bool:
        return not isinstance(self.spec, int)

    def _open(self) -> None:
        cv2 = self._cv2
        if cv2 is None:
            import cv2 as _cv2

            cv2 = self._cv2 = _cv2
        if self.is_file:
            cap = cv2.VideoCapture(str(self.spec))
        else:
            import sys

            api = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
            cap = cv2.VideoCapture(int(self.spec), api)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, 50)
        if not cap.isOpened():
            cap.release()
            raise OSError(f"kan ikke åpne {self.name}")
        self._cap = cap
        self.opened += 1
        self._last_frame = self.clock()
        self.last_error = None
        log.info("Video: %s åpnet", self.name)

    def read(self) -> Frame | None:
        now = self.clock()
        if self._cap is None:
            if now < self._next_open:
                return None
            try:
                self._open()
            except Exception as exc:
                self.last_error = str(exc)
                self._next_open = now + REOPEN_S
                return None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            if self.is_file and self.loop:
                self._cap.set(self._cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self._cap.read()
            if not ok or frame is None:
                if now - self._last_frame > STALL_S:
                    self.last_error = "ingen bilder fra kilden"
                    self.close()
                    self._next_open = now + REOPEN_S
                return None
        self._last_frame = now
        result: Frame = frame
        return result

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


Content = Literal["none", "desktop", "slide", "video"]


@dataclass
class SyntheticSource:
    """A drawn multiview, frame by frame. Tests change ``content``, ``slide`` and ``moving``."""

    mv: MultiviewMap
    width: int = 960
    height: int = 540
    content: Content = "slide"
    slide: int = 1
    moving: set[str] = field(default_factory=set)  # tile ids with movement
    black: bool = False  # the capture card lost the signal
    name: str = "syntetisk"
    _t: int = 0

    def _tile(self, frame: Frame, tile_id: str) -> tuple[int, int, int, int] | None:
        for t in self.mv.tiles:
            if t.id == tile_id:
                x, y, w, h = t.rect
                return (
                    round(y * self.height),
                    round((y + h) * self.height),
                    round(x * self.width),
                    round((x + w) * self.width),
                )
        return None

    def read(self) -> Frame | None:
        self._t += 1
        frame: Frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        if self.black:
            return frame
        rng = np.random.default_rng(self._t)
        for t in self.mv.tiles:
            y0, y1, x0, x1 = self._tile(frame, t.id) or (0, 0, 0, 0)
            area = frame[y0:y1, x0:x1]
            if t.camera is not None and t.camera.value == "LAPTOP":
                self._content(area, rng)
            elif t.source.startswith("input") or t.source in ("preview", "program"):
                area[:] = 90 + (hash(t.id) % 60)  # a camera: an even grey per tile
                cy, cx = area.shape[0] // 2, area.shape[1] // 2
                area[cy - 12 : cy + 12, cx - 8 : cx + 8] = 200  # a «person»
                if t.id in self.moving:
                    off = (self._t * 7) % max(1, area.shape[1] - 30)
                    area[10:40, off : off + 30] = 255
            else:
                area[:] = 20
            area[:2, :] = area[-2:, :] = 0  # the tally border the inset removes
            area[:, :2] = area[:, -2:] = 0
        return frame

    def _content(self, area: Frame, rng: np.random.Generator) -> None:
        h, w = area.shape[:2]
        if self.content == "none":
            area[:] = 0
        elif self.content == "desktop":
            area[:] = (120, 80, 40)
        elif self.content == "slide":
            area[:] = 235
            for i in range(4):  # lines of «text» that depend on the slide number
                y = 10 + i * (h // 5)
                length = (self.slide * 37 + i * 53) % (w - 20) + 10
                area[y : y + 6, 10 : 10 + length] = 30
        else:
            area[:] = rng.integers(0, 255, size=area.shape, dtype=np.uint8)

    def close(self) -> None:
        return None
