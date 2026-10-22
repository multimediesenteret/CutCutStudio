"""A video layer in the simulator (``cutcut sim --vision``): the drawn multiview follows the fake
ATEM, so the technician window shows cut-outs (D-056) and Helse shows H-VID-1/H-VID-3 without
a capture card. Runs inside the simulator's tick, through the same code as ``cutcut vision``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cutcut.common.ids import SourceId
from cutcut.common.models.multiview import MultiviewMap
from cutcut.core.runtime import CoreRuntime
from cutcut.vision.capture import SyntheticSource
from cutcut.vision.process import Vision

FRAME_MS = 66  # 15 Hz


@dataclass
class SimVision:
    mv: MultiviewMap
    runtime: CoreRuntime
    source: SyntheticSource = field(init=False)
    vision: Vision = field(init=False)
    wanted_until: int = -1
    _last_frame: int = -(10**9)
    _last_slow: int = -(10**9)
    _last_status: int = -(10**9)
    _last_thumbs: int = -(10**9)
    _last_faces: int = -(10**9)
    frames: int = 0

    def __post_init__(self) -> None:
        self.source = SyntheticSource(self.mv, width=960, height=540)
        self.vision = Vision(self.mv)
        self._tile_of = {t.camera: t.id for t in self.mv.tiles if t.camera is not None}

    def use_map(self, mv: MultiviewMap) -> None:
        """A new rutekart from the setup helper: read the drawn multiview with it. The drawing
        stays as it is: that is what the «ATEM» shows (VI-5)."""
        if mv != self.vision.mv:
            self.vision = Vision(mv)

    def want(self, now: int) -> None:
        self.wanted_until = now + 10_000

    def tick(
        self,
        now: int,
        program: SourceId | None,
        preview: SourceId | None,
        panning: set[str],
        talking: set[str] | None = None,
    ) -> None:
        if now - self._last_frame < FRAME_MS:
            return
        self._last_frame = now
        s = self.source
        s.program = self._tile_of.get(program, "W7") if program else "W7"
        s.preview = self._tile_of.get(preview, "W7") if preview else "W7"
        s.panning = {self._tile_of[SourceId(c)] for c in panning if SourceId(c) in self._tile_of}
        frame = s.read()
        if frame is None:
            return
        self.frames += 1
        rt = self.runtime
        rows = self.vision.measure(frame)
        rt.feed_bus("vision.frame", {"tiles": rows})
        if now - self._last_status >= 1000:
            self._last_status = now
            rt.feed_bus(
                "vision.status",
                {"source": "simulator", "fps": 15, "frames": self.frames, "faces": True},
            )
        if now - self._last_faces >= 200:  # P6: the drawn people have faces; a talker's
            self._last_faces = now  # mouth moves, so video_confirm and reactions can run
            for cam in self._tile_of:
                if cam is None or not cam.value.startswith("C") or cam is SourceId.C5:
                    continue
                speaking = talking is not None and cam.value in talking
                rt.feed_bus(
                    "vision.tile",
                    {
                        "source": cam.value,
                        "face": {"found": True, "size_ok": self._tile_of[cam] not in s.panning},
                        "mouth": 0.7 if speaking else 0.05,
                    },
                )
        if now - self._last_slow >= 200:
            self._last_slow = now
            rt.feed_bus("vision.moving", {"moving": self.vision.moving(now, rows)})
            pgm = self.vision.program(frame)
            if pgm is not None:
                rt.feed_bus("vision.pgm", pgm)
        if now < self.wanted_until and now - self._last_thumbs >= 500:
            self._last_thumbs = now
            thumbs: dict[str, Any] = self.vision.thumbnails(frame)
            if thumbs:
                rt.feed_bus("vision.thumbs", {"thumbs": thumbs})
