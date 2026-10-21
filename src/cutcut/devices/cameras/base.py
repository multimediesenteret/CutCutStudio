"""The camera driver interface (spec 7.3) and the commands CutCut sends to cameras (CA-1).

Every driver (``obsbot``, ``canon_xc``, later Panasonic and Sony) implements
:class:`CameraDriver`. A function a camera lacks raises :class:`Unsupported`, and the screens
hide that button. Drivers are never called directly: :class:`~.guarded.GuardedCamera` wraps
each one with the on-air guard (I2, ``PV2``), the limits, one queue and a circuit breaker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from cutcut.common.ids import CameraId
from cutcut.common.models.site import CameraLimits

__all__ = [
    "AutoTracking",
    "CameraCommand",
    "CameraDriver",
    "CameraError",
    "CameraLimits",
    "CameraStatus",
    "Exposure",
    "MoveTo",
    "Nudge",
    "PTZPosition",
    "RecallPreset",
    "StorePreset",
    "Unsupported",
    "WhiteBalance",
    "ZoomTo",
    "moves_or_colours",
    "send",
]


class CameraError(Exception):
    """The camera did not answer, or answered with an error."""


class Unsupported(CameraError):  # noqa: N818 – the name in spec 7.3
    """This camera has no such function (the screens hide the button)."""


@dataclass(frozen=True)
class PTZPosition:
    pan: float  # degrees from home, + is right
    tilt: float  # degrees from home, + is up
    zoom: float  # 0 widest … 1 tightest


@dataclass(frozen=True)
class CameraStatus:
    online: bool
    mode: str = ""  # e.g. «manuell», «AI-tracking»
    last_error: str | None = None


class CameraDriver(Protocol):
    """Spec 7.3, plus ``move_to``/``zoom_to`` for small framing changes (plan CA-1)."""

    id: CameraId

    async def connect(self) -> None: ...
    async def status(self) -> CameraStatus: ...
    async def recall_preset(self, n: int, speed: float = 0.5) -> None: ...
    async def store_preset(self, n: int) -> None: ...
    async def nudge(self, pan: float, tilt: float, zoom: float) -> None: ...
    async def move_to(self, pan: float, tilt: float, speed: float) -> None: ...
    async def zoom_to(self, zoom: float, speed: float) -> None: ...
    async def position(self) -> PTZPosition | None: ...
    async def set_white_balance(
        self, kelvin: int | None = None, r: int | None = None, b: int | None = None
    ) -> None: ...
    async def set_exposure(
        self, iris: float | None = None, gain_db: float | None = None, shutter: str | None = None
    ) -> None: ...
    async def set_auto_tracking(self, on: bool) -> None: ...


# --- commands ------------------------------------------------------------------------------


@dataclass(frozen=True)
class RecallPreset:
    n: int
    speed: float = 0.5
    kind: Literal["recall_preset"] = "recall_preset"


@dataclass(frozen=True)
class StorePreset:
    """Only from the setup helper. Saves where the camera points; does not move it."""

    n: int
    kind: Literal["store_preset"] = "store_preset"


@dataclass(frozen=True)
class Nudge:
    """Small relative steps, each −1…1 (spec 7.3)."""

    pan: float = 0.0
    tilt: float = 0.0
    zoom: float = 0.0
    kind: Literal["nudge"] = "nudge"


@dataclass(frozen=True)
class MoveTo:
    pan: float
    tilt: float
    speed: float = 0.3
    kind: Literal["move_to"] = "move_to"


@dataclass(frozen=True)
class ZoomTo:
    zoom: float
    speed: float = 0.3
    kind: Literal["zoom_to"] = "zoom_to"


@dataclass(frozen=True)
class WhiteBalance:
    kelvin: int | None = None
    r: int | None = None
    b: int | None = None
    kind: Literal["white_balance"] = "white_balance"


@dataclass(frozen=True)
class Exposure:
    iris: float | None = None
    gain_db: float | None = None
    shutter: str | None = None
    kind: Literal["exposure"] = "exposure"


@dataclass(frozen=True)
class AutoTracking:
    on: bool
    kind: Literal["auto_tracking"] = "auto_tracking"


CameraCommand = (
    RecallPreset | StorePreset | Nudge | MoveTo | ZoomTo | WhiteBalance | Exposure | AutoTracking
)


def moves_or_colours(cmd: CameraCommand) -> bool:
    """Would the picture change? Those are refused on program and preview (I2, ``PV2``).

    Saving a preset does not move the camera. Turning AI-tracking *off* stops movement, so it
    is always allowed (``AT6``: off at start and end of every session)."""
    if isinstance(cmd, StorePreset):
        return False
    if isinstance(cmd, AutoTracking):
        return cmd.on
    return True


async def send(driver: CameraDriver, cmd: CameraCommand) -> None:
    """Carry out one command on the driver."""
    match cmd:
        case RecallPreset(n=n, speed=speed):
            await driver.recall_preset(n, speed)
        case StorePreset(n=n):
            await driver.store_preset(n)
        case Nudge(pan=p, tilt=t, zoom=z):
            await driver.nudge(p, t, z)
        case MoveTo(pan=p, tilt=t, speed=speed):
            await driver.move_to(p, t, speed)
        case ZoomTo(zoom=z, speed=speed):
            await driver.zoom_to(z, speed)
        case WhiteBalance(kelvin=k, r=r, b=b):
            await driver.set_white_balance(k, r, b)
        case Exposure(iris=i, gain_db=g, shutter=s):
            await driver.set_exposure(i, g, s)
        case AutoTracking(on=on):
            await driver.set_auto_tracking(on)
