"""All PTZ cameras in ``core`` (CA-6): one ``GuardedCamera`` each, and the polls that feed the
engine and the health page.

* Every 2 s the position of each camera is read. A camera whose position changed is *moving*
  (``S1`` holds it back) until a poll finds it still. If it moved without CutCut asking, and
  AI-tracking is off, that is ``H-CAM-MOVE`` (spec 8.5): someone or something moved it.
* Every 10 s each camera is asked how it is: online, manual white balance and exposure, and
  how fast it answers (``H-CAM-*``).
* At start AI-tracking is turned off on every camera (``AT6``).

The polls only read; nothing here moves a camera. Commands come from the engine and the
screens through :meth:`submit`, and the guard decides whether they may reach the camera.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final

from cutcut.common.ids import CameraId
from cutcut.common.models.site import CameraDevice, Devices
from cutcut.devices.cameras.base import (
    AutoTracking,
    CameraCommand,
    CameraDriver,
    PTZPosition,
    RecallPreset,
    ZoomTo,
)
from cutcut.devices.cameras.factory import make_driver
from cutcut.devices.cameras.guarded import GuardedCamera, OnAir, Verdict

log = logging.getLogger(__name__)

POLL_S: Final = 2.0  # spec 8.5: H-CAM-MOVE reads the position every 2 s
STATUS_S: Final = 10.0  # H-CAM-*
MOVE_DEG: Final = 0.5  # less than this is noise in the read-back
MOVE_ZOOM: Final = 0.01
SETTLE_S: Final = 15.0  # a slow preset move CutCut asked for may still be under way
FRAME_SPEED: Final = 0.3  # F2: reframing off air, slow enough to look calm on the multiview
ZOOM_STEP: Final = 0.01  # Z1: one step of a slow zoom, share of the zoom range


def moved(a: PTZPosition, b: PTZPosition) -> bool:
    return (
        abs(a.pan - b.pan) >= MOVE_DEG
        or abs(a.tilt - b.tilt) >= MOVE_DEG
        or abs(a.zoom - b.zoom) >= MOVE_ZOOM
    )


@dataclass
class CameraService:
    guards: dict[CameraId, GuardedCamera]
    models: dict[CameraId, str] = field(default_factory=dict)
    air: Callable[[], OnAir | None] = field(default=lambda: None)  # from the ATEM read-back
    clock: Callable[[], float] = time.monotonic
    on_moving: Callable[[frozenset[CameraId]], None] | None = None
    moving: frozenset[CameraId] = frozenset()
    unexpected: dict[CameraId, float] = field(default_factory=dict)  # when it moved by itself
    started: float | None = None
    _tasks: dict[CameraId, asyncio.Task[None]] = field(default_factory=dict)
    _zooms: dict[CameraId, asyncio.Task[None]] = field(default_factory=dict)

    @classmethod
    def from_devices(
        cls,
        devices: Devices,
        air: Callable[[], OnAir | None],
        *,
        make: Callable[[CameraId, CameraDevice], CameraDriver | None] = make_driver,
        clock: Callable[[], float] = time.monotonic,
    ) -> CameraService:
        guards: dict[CameraId, GuardedCamera] = {}
        models: dict[CameraId, str] = {}
        for cam, dev in devices.cameras.items():
            driver = make(cam, dev)
            if driver is not None:
                guards[cam] = GuardedCamera(driver, dev.limits, air, clock=clock)
                models[cam] = dev.model
        return cls(guards, models, air, clock)

    def reconfigure(
        self,
        devices: Devices,
        *,
        make: Callable[[CameraId, CameraDevice], CameraDriver | None] = make_driver,
    ) -> None:
        """New addresses from the technician window (D-055): cameras whose address or model
        changed get a new driver; the others keep theirs."""
        for cam, dev in devices.cameras.items():
            old = self.guards.get(cam)
            host = getattr(old.driver, "host", None) if old else None
            same = old is not None and host == (str(dev.ip) if dev.ip else None)
            if same and self.models.get(cam) == dev.model:
                continue
            if old is not None:
                self._drop(cam)
            driver = make(cam, dev)
            if driver is None:
                continue
            g = GuardedCamera(driver, dev.limits, self.air, clock=self.clock)
            self.guards[cam], self.models[cam] = g, dev.model
            if self.started is not None:
                self._tasks[cam] = asyncio.create_task(g.run(), name=f"camera-{cam.value}")
                g.submit(AutoTracking(on=False))
            log.info("%s: ny adresse %s tatt i bruk", cam.value, dev.ip)

    def _drop(self, cam: CameraId) -> None:
        g = self.guards.pop(cam, None)
        self.models.pop(cam, None)
        task = self._tasks.pop(cam, None)
        if task is not None:
            task.cancel()
        close = getattr(g.driver, "close", None) if g else None
        if close is not None:
            with contextlib.suppress(Exception):
                close()

    # --- commands ----------------------------------------------------------------------------

    def submit(self, cam: CameraId, cmd: CameraCommand) -> Verdict | None:
        """Queue ``cmd`` for ``cam``; ``None`` when CutCut does not steer that camera."""
        g = self.guards.get(cam)
        return None if g is None else g.submit(cmd)

    # --- framing and slow zoom from the engine (F1, Z1, Z2) ---------------------------------

    def frame(self, cam: CameraId, preset: int) -> Verdict | None:
        """F1: recall a framing preset. The guard refuses it on program or preview (I2)."""
        return self.submit(cam, RecallPreset(preset, speed=FRAME_SPEED))

    def slow_zoom(self, cam: CameraId, amount: float, duration_s: float) -> bool:
        """Z1: zoom in by ``amount`` over ``duration_s`` in small steps at the camera's slow
        speed. Each step passes the guard on its own (I2's one exception)."""
        g = self.guards.get(cam)
        if g is None:
            return False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            log.info("%s: langsom zoom uten hendelsesløkke, hoppet over", cam.value)
            return False
        self.stop_zoom(cam)
        self._zooms[cam] = loop.create_task(
            self._zoom(g, amount, duration_s), name=f"zoom-{cam.value}"
        )
        return True

    async def _zoom(self, g: GuardedCamera, amount: float, duration_s: float) -> None:
        start = g.st.position or await g.refresh()
        if start is None:
            return
        steps = max(1, round(amount / ZOOM_STEP))
        for i in range(1, steps + 1):
            target = min(g.limits.zoom[1], start.zoom + amount * i / steps)
            if g.submit(ZoomTo(target, speed=g.limits.slow_zoom_speed, slow=True)) != "queued":
                return  # refused (switch off, camera off air …): stop quietly
            await asyncio.sleep(duration_s / steps)

    def stop_zoom(self, cam: CameraId) -> None:
        """Z2: stop a slow zoom at once."""
        task = self._zooms.pop(cam, None)
        if task is not None:
            task.cancel()

    # --- polls -------------------------------------------------------------------------------

    def _expected(self, g: GuardedCamera) -> bool:
        if g.st.tracking:
            return True
        t = g.st.moved_by_us_at
        return t is not None and self.clock() - t < SETTLE_S

    async def _poll_one(self, cam: CameraId, g: GuardedCamera) -> bool:
        before = g.st.position
        after = await g.refresh()
        if before is None or after is None or g.st.position_at is None:
            return False
        if not moved(before, after):
            return False
        if not self._expected(g):
            self.unexpected[cam] = self.clock()
            log.error(
                "%s har flyttet seg uten at CutCut ba om det: %s → %s", cam.value, before, after
            )
        return True

    async def poll_positions(self) -> frozenset[CameraId]:
        cams = list(self.guards.items())
        results = await asyncio.gather(*(self._poll_one(c, g) for c, g in cams))
        self.moving = frozenset(c for (c, _), m in zip(cams, results, strict=True) if m)
        if self.on_moving is not None:
            self.on_moving(self.moving)
        return self.moving

    async def poll_status(self) -> None:
        await asyncio.gather(*(g.read_status() for g in self.guards.values()))

    async def run(self) -> None:
        """Run the guards' queues and the polls until cancelled."""
        self.started = self.clock()
        for cam, g in self.guards.items():
            self._tasks[cam] = asyncio.create_task(g.run(), name=f"camera-{cam.value}")
            g.submit(AutoTracking(on=False))  # AT6: off at start
        last_status = -STATUS_S
        try:
            while True:
                try:
                    if self.clock() - last_status >= STATUS_S:
                        last_status = self.clock()
                        await self.poll_status()
                    await self.poll_positions()
                except Exception:  # a poll must never take core down
                    log.exception("kamerasjekken feilet")
                await asyncio.sleep(POLL_S)
        finally:
            for t in self._tasks.values():
                t.cancel()
            self._tasks.clear()

    def close(self) -> None:
        for g in self.guards.values():
            close = getattr(g.driver, "close", None)
            if close is not None:
                with contextlib.suppress(Exception):
                    close()
