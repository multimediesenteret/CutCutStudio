"""A fake PTZ camera in the process (CA-1): implements ``CameraDriver`` and remembers every
command that reached it, so tests can prove what never did (I2). Network fakes that speak
VISCA, OSC and XC come with the real drivers (CA-2–CA-4) and use the same state."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from cutcut.common.ids import CameraId
from cutcut.devices.cameras.base import CameraError, CameraStatus, PTZPosition


@dataclass
class FakeCamera:
    id: CameraId
    pan: float = 0.0
    tilt: float = 0.0
    zoom: float = 0.0
    presets: dict[int, PTZPosition] = field(default_factory=dict)
    kelvin: int = 5600
    tracking: bool = False
    down: bool = False  # answers nothing
    delay_s: float = 0.0  # a slow camera
    received: list[str] = field(default_factory=list)

    async def _io(self, what: str) -> None:
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.down:
            raise CameraError("svarer ikke")
        self.received.append(what)

    @property
    def moved(self) -> list[str]:
        """Commands that changed the picture."""
        keep = ("store", "status", "position", "connect", "tracking False")
        return [r for r in self.received if not r.startswith(keep)]

    async def connect(self) -> None:
        await self._io("connect")

    async def status(self) -> CameraStatus:
        await self._io("status")
        return CameraStatus(online=True, mode="AI-tracking" if self.tracking else "manuell")

    async def recall_preset(self, n: int, speed: float = 0.5) -> None:
        await self._io(f"recall {n} {speed:g}")
        if n in self.presets:
            p = self.presets[n]
            self.pan, self.tilt, self.zoom = p.pan, p.tilt, p.zoom

    async def store_preset(self, n: int) -> None:
        await self._io(f"store {n}")
        self.presets[n] = PTZPosition(self.pan, self.tilt, self.zoom)

    async def nudge(self, pan: float, tilt: float, zoom: float) -> None:
        await self._io(f"nudge {pan:g} {tilt:g} {zoom:g}")
        self.pan += pan * 5
        self.tilt += tilt * 5
        self.zoom = min(max(self.zoom + zoom * 0.05, 0.0), 1.0)

    async def move_to(self, pan: float, tilt: float, speed: float) -> None:
        await self._io(f"move {pan:g} {tilt:g} {speed:g}")
        self.pan, self.tilt = pan, tilt

    async def zoom_to(self, zoom: float, speed: float) -> None:
        await self._io(f"zoom {zoom:g} {speed:g}")
        self.zoom = zoom

    async def position(self) -> PTZPosition | None:
        await self._io("position")
        return PTZPosition(self.pan, self.tilt, self.zoom)

    async def set_white_balance(
        self, kelvin: int | None = None, r: int | None = None, b: int | None = None
    ) -> None:
        await self._io(f"wb {kelvin} {r} {b}")
        if kelvin is not None:
            self.kelvin = kelvin

    async def set_exposure(
        self, iris: float | None = None, gain_db: float | None = None, shutter: str | None = None
    ) -> None:
        await self._io(f"exposure {iris} {gain_db} {shutter}")

    async def set_auto_tracking(self, on: bool) -> None:
        await self._io(f"tracking {on}")
        self.tracking = on
