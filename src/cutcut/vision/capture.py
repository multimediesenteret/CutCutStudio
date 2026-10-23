"""Where the multiview picture comes from (VI-1).

* :class:`OpenCvSource` – the capture device through DirectShow, or a video file. In the
  studio that is the INOGENI 4KXUSB3 or the ATEM's own webcam output (D-071); both are UVC
  devices without a driver, found by part of their DirectShow name («INOGENI», «Blackmagic
  Design») so the number can change without a setting. :meth:`OpenCvSource.use_device`
  changes the device while running (``vision.source`` from core). Frames are taken at 15 Hz;
  the rest are dropped early to save CPU. A device that stops delivering is opened again every
  5 s, forever.
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


def dshow_devices() -> list[str]:
    """DirectShow video inputs in the order OpenCV numbers them (Windows, pygrabber). Empty
    elsewhere or when the list cannot be read."""
    try:
        from pygrabber.dshow_graph import FilterGraph  # type: ignore[import-not-found]
    except ImportError:
        return []
    try:
        return [str(n) for n in FilterGraph().get_input_devices()]
    except Exception as exc:  # COM errors: fall back to the index
        log.warning("Video: kan ikke liste DirectShow-enheter: %s", exc)
        return []


def find_device(name: str, devices: list[str]) -> int | None:
    """Index of the first device whose name contains ``name`` (case-insensitive)."""
    want = name.casefold()
    return next((i for i, d in enumerate(devices) if want and want in d.casefold()), None)


class OpenCvSource:
    """A capture device (index, or found by name) or a file (path) through OpenCV."""

    def __init__(
        self,
        spec: int | str,
        *,
        width: int = 1920,
        height: int = 1080,
        fps: int = 50,
        device_name: str | None = None,
        list_devices: Callable[[], list[str]] = dshow_devices,
        loop: bool = True,
        clock: Callable[[], float] = time.monotonic,
        cv2: Any = None,
    ) -> None:
        self.spec = spec
        self.width, self.height, self.fps = width, height, fps
        self.device_name = device_name
        self.list_devices = list_devices
        self.found_as: str | None = None  # the DirectShow name that matched
        self.loop = loop
        self.clock = clock
        self._cv2 = cv2
        if isinstance(spec, int):
            self.name = f"«{device_name}»" if device_name else f"enhet {spec}"
        else:
            self.name = f"fil {spec}"
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
            cap = cv2.VideoCapture(self._index(), api)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, self.fps)
        if not cap.isOpened():
            cap.release()
            raise OSError(f"kan ikke åpne {self.name}")
        self._cap = cap
        self.opened += 1
        self._last_frame = self.clock()
        self.last_error = None
        log.info("Video: %s åpnet", self.name)

    def _index(self) -> int:
        """The device by name when one is given and found, else the index."""
        if self.device_name:
            devices = self.list_devices()
            i = find_device(self.device_name, devices)
            if i is not None:
                self.found_as = devices[i]
                return i
            if devices:
                log.warning(
                    "Video: fant ingen enhet med «%s» i navnet (%s); bruker nummer %s",
                    self.device_name,
                    ", ".join(devices),
                    self.spec,
                )
        return int(self.spec)

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

    def use_device(self, name: str) -> bool:
        """Open the device with ``name`` in its DirectShow name from the next read (the capture
        method chosen on the setup screen, D-071). True when it changed."""
        if self.is_file or not name or name == self.device_name:
            return False
        self.close()
        self.device_name = name
        self.name = f"«{name}»"
        self.found_as = None
        self.last_error = None
        self._next_open = 0.0
        log.info("Video: bytter til %s", self.name)
        return True

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


Content = Literal["none", "desktop", "slide", "cursor", "video"]


@dataclass
class SyntheticSource:
    """A drawn multiview, frame by frame. Tests change ``content``, ``slide`` and ``moving``."""

    mv: MultiviewMap
    width: int = 960
    height: int = 540
    content: Content = "slide"
    slide: int = 1
    moving: set[str] = field(default_factory=set)  # tile ids where someone moves
    panning: set[str] = field(default_factory=set)  # tile ids whose camera pans
    program: str = "W1"  # which camera tile the program window shows
    preview: str = "W2"
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
            elif t.source.startswith("input"):
                self._camera(area, t.id)
            elif t.source in ("program", "preview"):
                shown = self.program if t.source == "program" else self.preview
                if any(x.id == shown and x.source.startswith("input") for x in self.mv.tiles):
                    self._camera(area, shown)
                else:
                    area[:] = 20  # a graphic or black (media player, «Kun lyd»)
            else:
                area[:] = 20
            area[:2, :] = area[-2:, :] = 0  # the tally border the inset removes
            area[:, :2] = area[:, -2:] = 0
        return frame

    def _camera(self, area: Frame, tile_id: str) -> None:
        """A camera picture that only this tile shows: a «person» placed by the tile id, the
        same at any size (so the program window can be matched with it)."""
        h, w = area.shape[:2]
        seed = sum(ord(c) for c in tile_id)
        area[:] = 70 + (seed * 13) % 90
        px = (0.2 + (seed % 7) / 10) * w
        py = (0.25 + (seed % 3) / 10) * h
        area[int(py) : int(py + 0.45 * h), int(px) : int(px + 0.18 * w)] = 210
        area[int(0.8 * h) :, :] = 40 + (seed * 7) % 50  # the table
        # a wall with texture (stripes in picture coordinates: the same at any size)
        stripes = 45 * np.sin(np.linspace(0, 2 * np.pi * (6 + seed % 5), w))
        wall = area[: int(0.25 * h)].astype(np.int16) + stripes[None, :, None].astype(np.int16)
        area[: int(0.25 * h)] = wall.clip(0, 255).astype(np.uint8)
        area[int(0.25 * h) : int(0.8 * h)] = (
            (
                area[int(0.25 * h) : int(0.8 * h)].astype(np.int16)
                + (stripes[None, :, None] * 0.8).astype(np.int16)
            )
            .clip(0, 255)
            .astype(np.uint8)
        )
        if tile_id in self.panning:  # the whole picture slides sideways
            area[:] = np.roll(area, (self._t * max(3, w // 25)) % w, axis=1)
        if tile_id in self.moving:  # someone gestures: a small part changes
            off = (self._t * 7) % max(1, w - 30)
            area[10:40, off : off + 30] = 255

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
            # a picture on the slide, left or right: a new slide changes well over 15 %
            x0 = w // 2 if self.slide % 2 else 0
            area[h // 3 : h - 4, x0 + 4 : x0 + w // 2 - 4] = (40, 120, 200)
        elif self.content == "cursor":
            area[:] = 235
            cx = (self._t * 3) % max(1, w - 8)
            area[h // 2 : h // 2 + 8, cx : cx + 8] = 0  # only the mouse moves
        else:
            area[:] = rng.integers(0, 255, size=area.shape, dtype=np.uint8)

    def close(self) -> None:
        return None
