"""``GuardedCamera``: the only way CutCut talks to a camera (CA-1, I2, ``PV2``, ADR-0005).

* **On-air guard.** A command that would move the camera or change its colour is refused while
  the camera is on program or preview. What is on air comes from the ATEM read-back, not from
  the engine, so the guard holds also when the engine is wrong. If the ATEM cannot be read,
  every such command is refused. The check runs twice: when the command is queued and again
  right before it is sent, because the ATEM may have cut in between.
* **Limits.** Pan, tilt, zoom and speed are clamped to the camera's ``CameraLimits`` and the
  clamping is logged (8.4).
* **One queue** per camera, so a slow camera never blocks the engine or the other cameras.
  ``submit`` only queues; ``run`` sends one command at a time with a 200 ms timeout.
* **Circuit breaker.** Three failures in a row open it for 10 s; the camera counts as down.

Nothing here decides what to do with a camera; it only carries out what it is asked (I3).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from typing import Final, Literal

from cutcut.common.ids import CameraId, RuleId, SourceId
from cutcut.common.models.site import CameraLimits
from cutcut.core.inputs import AtemReadback
from cutcut.devices.cameras.base import (
    CameraCommand,
    CameraDriver,
    MoveTo,
    Nudge,
    PTZPosition,
    RecallPreset,
    StorePreset,
    Unsupported,
    ZoomTo,
    moves_or_colours,
    send,
)

log = logging.getLogger(__name__)

TIMEOUT_S: Final = 0.2
FAILS_TO_OPEN: Final = 3
OPEN_S: Final = 10.0
MAX_QUEUE: Final = 8
PRESETS: Final = range(256)  # VISCA 00–FF

Verdict = Literal["queued", "on_program", "on_preview", "no_atem", "breaker_open", "invalid"]


@dataclass(frozen=True)
class OnAir:
    """Cameras the ATEM shows on program and on preview right now."""

    program: frozenset[CameraId]
    preview: frozenset[CameraId]


def on_air(rb: AtemReadback | None, cameras: Iterable[CameraId]) -> OnAir | None:
    """What is on air from the ATEM read-back. ``None`` when the ATEM cannot be read.

    A SuperSource layout shows several cameras, and which ones is not read back yet (M4), so
    then every camera counts as on air: better a camera that waits than one that moves on air.
    """
    if rb is None:
        return None
    every = frozenset(cameras)

    def cams(src: SourceId) -> frozenset[CameraId]:
        if src is SourceId.SUPERSOURCE:
            return every
        return (
            frozenset({CameraId(src.value)}) if src.value in CameraId.__members__ else frozenset()
        )

    return OnAir(program=cams(rb.program), preview=cams(rb.preview))


@dataclass
class GuardStatus:
    ok: bool = True  # False while the circuit breaker is open
    sent: int = 0
    failed: int = 0
    refused: int = 0
    clamped: int = 0
    dropped: int = 0
    unsupported: int = 0
    last_error: str | None = None
    last_refused: str | None = None
    open_until: float = 0.0
    queue: int = 0
    position: PTZPosition | None = None


@dataclass
class GuardedCamera:
    driver: CameraDriver
    limits: CameraLimits
    air: Callable[[], OnAir | None]  # from the ATEM read-back, never from the engine
    guard_preview: bool = True  # PV2: a camera on preview counts as on air
    clock: Callable[[], float] = time.monotonic
    timeout_s: float = TIMEOUT_S
    _queue: deque[CameraCommand] = field(default_factory=deque, init=False)
    _wake: asyncio.Event | None = field(default=None, init=False)
    _fails: int = field(default=0, init=False)
    st: GuardStatus = field(default_factory=GuardStatus, init=False)

    @property
    def id(self) -> CameraId:
        return self.driver.id

    # --- the guard ---------------------------------------------------------------------------

    def blocked(self, cmd: CameraCommand) -> Verdict | None:
        """Why ``cmd`` may not reach the camera now (I2, ``PV2``), or ``None``."""
        if not moves_or_colours(cmd):
            return None
        air = self.air()
        if air is None:
            return "no_atem"
        if self.id in air.program:
            return "on_program"
        if self.guard_preview and self.id in air.preview:
            return "on_preview"
        return None

    def _refuse(self, cmd: CameraCommand, why: Verdict) -> Verdict:
        self.st.refused += 1
        text = {
            "on_program": "på program (I2)",
            "on_preview": f"på preview ({RuleId.PV2.value})",
            "no_atem": "ATEM kan ikke leses",
        }.get(why, why)
        self.st.last_refused = f"{cmd.kind}: {text}"
        log.info("%s: %s avvist, kameraet er %s", self.id, cmd.kind, text)
        return why

    # --- limits ------------------------------------------------------------------------------

    def clamp(self, cmd: CameraCommand) -> CameraCommand:
        """``cmd`` within the limits. Logs when anything had to change (8.4)."""
        lim = self.limits

        def c(v: float, lo: float, hi: float) -> float:
            return min(max(v, lo), hi)

        top = lim.max_speed
        out: CameraCommand = cmd
        match cmd:
            case RecallPreset(speed=s):
                out = replace(cmd, speed=c(s, 0.01, top))
            case MoveTo(pan=p, tilt=t, speed=s):
                out = replace(cmd, pan=c(p, *lim.pan), tilt=c(t, *lim.tilt), speed=c(s, 0.01, top))
            case ZoomTo(zoom=z, speed=s):
                out = replace(cmd, zoom=c(z, *lim.zoom), speed=c(s, 0.01, top))
            case Nudge(pan=p, tilt=t, zoom=z):
                p, t, z = c(p, -1, 1), c(t, -1, 1), c(z, -1, 1)
                at = self.st.position
                if at is not None:  # already at a limit: no step further out
                    if (p > 0 and at.pan >= lim.pan[1]) or (p < 0 and at.pan <= lim.pan[0]):
                        p = 0.0
                    if (t > 0 and at.tilt >= lim.tilt[1]) or (t < 0 and at.tilt <= lim.tilt[0]):
                        t = 0.0
                    if (z > 0 and at.zoom >= lim.zoom[1]) or (z < 0 and at.zoom <= lim.zoom[0]):
                        z = 0.0
                out = replace(cmd, pan=p, tilt=t, zoom=z)
        if out != cmd:
            self.st.clamped += 1
            log.warning("%s: %s klemt til grensene: %s → %s", self.id, cmd.kind, cmd, out)
        return out

    # --- queue -------------------------------------------------------------------------------

    def submit(self, cmd: CameraCommand) -> Verdict:
        """Queue ``cmd``. Never waits; says straight away when it will not be sent."""
        if isinstance(cmd, RecallPreset | StorePreset) and cmd.n not in PRESETS:
            return "invalid"
        why = self.blocked(cmd)
        if why is not None:
            return self._refuse(cmd, why)
        if self.clock() < self.st.open_until:
            return "breaker_open"
        self._queue.append(self.clamp(cmd))
        while len(self._queue) > MAX_QUEUE:  # a camera that lags: the oldest is stale
            self._queue.popleft()
            self.st.dropped += 1
        self.st.queue = len(self._queue)
        if self._wake is not None:
            self._wake.set()
        return "queued"

    async def step(self) -> bool:
        """Send the next command, if any. Returns whether one was taken from the queue."""
        if not self._queue:
            return False
        cmd = self._queue.popleft()
        self.st.queue = len(self._queue)
        why = self.blocked(cmd)  # the ATEM may have cut since it was queued
        if why is not None:
            self._refuse(cmd, why)
            return True
        try:
            await asyncio.wait_for(send(self.driver, cmd), self.timeout_s)
        except (Unsupported, ValueError) as e:  # no such function, or a value it cannot take:
            # the camera is not broken, so this does not count towards the circuit breaker
            self.st.unsupported += 1
            self.st.last_error = f"{cmd.kind}: {e}"
            log.info("%s: %s", self.id, self.st.last_error)
            return True
        except Exception as e:
            self._failed(f"{cmd.kind}: {self._why(e)}")
            return True
        self._fails = 0
        self.st.ok = True
        self.st.sent += 1
        if moves_or_colours(cmd):
            await self.refresh()
        return True

    async def refresh(self) -> PTZPosition | None:
        """Read where the camera points (for the limits, ``S1`` and ``H-CAM-MOVE``)."""
        try:
            self.st.position = await asyncio.wait_for(self.driver.position(), self.timeout_s)
        except Exception as e:
            self._failed(f"posisjon: {self._why(e)}")
        return self.st.position

    def _why(self, e: Exception) -> str:
        if isinstance(e, TimeoutError):
            return f"svarte ikke innen {self.timeout_s * 1000:.0f} ms"
        return str(e) or type(e).__name__

    def _failed(self, why: str) -> None:
        self._fails += 1
        self.st.failed += 1
        self.st.last_error = why
        log.warning("%s: %s", self.id, why)
        if self._fails >= FAILS_TO_OPEN:
            self.st.ok = False
            self.st.open_until = self.clock() + OPEN_S
            self._queue.clear()
            self.st.queue = 0
            self._fails = 0
            log.error("%s svarer ikke; prøver igjen om %.0f s", self.id, OPEN_S)

    async def run(self) -> None:
        """Send queued commands until cancelled."""
        self._wake = asyncio.Event()
        while True:
            if not await self.step():
                self._wake.clear()
                await self._wake.wait()
