"""Pearl as the studio's recorder (spec 7.4, SE-2, SE-3).

Implements :class:`cutcut.app.studio.Recorder` without ever blocking the engine:

* ``start``/``stop`` only queue a command and return at once. They are idempotent: starting
  a recorder that is starting or started sends nothing (ADR-0005).
* A worker thread sends commands and polls the recorder status every 2 s (at once after a
  command), storage every 30 s and the firmware once. ``state`` is always the last answer
  from the Pearl – the session manager compares it with what it asked for, and raises the
  alarm if a recording stops by itself. CutCut never stops a recording on its own (I7).
* If the Pearl has not answered for a while, ``start`` returns False so the touch screen
  can say at once that recording cannot start, instead of waiting for the 10 s timeout.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, Literal, Protocol

from cutcut.common.models.session import RecordingStatus
from cutcut.devices.pearl.client import PearlError, RecorderInfo, StorageInfo

log = logging.getLogger(__name__)

STATUS_EVERY_S: Final = 2.0
STORAGE_EVERY_S: Final = 30.0
OFFLINE_AFTER_S: Final = 6.0
START_GRACE_S: Final = 10.0  # same as the session manager's start timeout


class PearlApi(Protocol):
    def recorder_status(self, rid: str) -> RecorderInfo: ...
    def start(self, rid: str) -> None: ...
    def stop(self, rid: str) -> None: ...
    def storages(self) -> list[StorageInfo]: ...
    def firmware(self) -> str: ...


@dataclass
class PearlStatus:
    online: bool
    state: RecordingStatus
    duration_s: int
    last_error: str | None
    firmware: str | None
    storages: list[StorageInfo]


@dataclass
class PearlRecorder:
    api: PearlApi
    recorder_id: str = "1"
    clock: Callable[[], float] = time.monotonic
    start_thread: bool = True

    state: RecordingStatus = field(init=False, default=RecordingStatus.IDLE)
    duration_s: int = field(init=False, default=0)
    last_error: str | None = field(init=False, default=None)
    firmware: str | None = field(init=False, default=None)
    storages: list[StorageInfo] = field(init=False, default_factory=list)
    _pending: Literal["start", "stop"] | None = field(init=False, default=None)
    _last_ok: float | None = field(init=False, default=None)
    _next_status: float = field(init=False, default=0.0)
    _next_storage: float = field(init=False, default=0.0)
    _cv: threading.Condition = field(init=False, default_factory=threading.Condition)
    _stop: bool = field(init=False, default=False)
    _start_sent: float | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self._started_at = self.clock()
        self._thread: threading.Thread | None = None
        if self.start_thread:
            self._thread = threading.Thread(target=self._run, name="pearl", daemon=True)
            self._thread.start()

    # -- Recorder protocol (called from the engine thread; never blocks) -----------------

    def online(self) -> bool:
        if self._last_ok is None:
            return self.clock() - self._started_at < OFFLINE_AFTER_S  # benefit of the doubt
        return self.clock() - self._last_ok < OFFLINE_AFTER_S

    def start(self, now: int) -> bool:
        with self._cv:
            if not self.online():
                return False
            if self.state in (RecordingStatus.STARTING, RecordingStatus.STARTED):
                return True  # idempotent
            self._pending = "start"
            self.state = RecordingStatus.STARTING
            self._next_status = 0.0
            self._cv.notify()
            return True

    def stop(self, now: int) -> bool:
        with self._cv:
            if self.state in (RecordingStatus.STOPPED, RecordingStatus.IDLE) and not self._pending:
                return True  # idempotent
            self._pending = "stop"
            self._next_status = 0.0
            self._cv.notify()
            return True

    def update(self, now: int) -> None:
        return None  # the worker thread keeps ``state`` current

    def status(self) -> PearlStatus:
        with self._cv:
            return PearlStatus(
                online=self.online(),
                state=self.state,
                duration_s=self.duration_s,
                last_error=self.last_error,
                firmware=self.firmware,
                storages=list(self.storages),
            )

    # -- worker ---------------------------------------------------------------------------

    def close(self) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify()
        if self._thread is not None:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        while True:
            with self._cv:
                if self._stop:
                    return
                wait = max(0.0, min(self._next_status, self._next_storage) - self.clock())
                if self._pending is None and wait > 0:
                    self._cv.wait(timeout=min(wait, 0.5))
                    continue
            self.step()

    def step(self) -> None:
        """One round: send a pending command, then poll what is due. Public for tests."""
        with self._cv:
            command, self._pending = self._pending, None
        now = self.clock()
        try:
            if command == "start":
                self.api.start(self.recorder_id)
                with self._cv:
                    self._start_sent = now
            elif command == "stop":
                self.api.stop(self.recorder_id)
            if self.firmware is None:
                fw = self.api.firmware()
                with self._cv:
                    self.firmware = fw
            if command is not None or now >= self._next_status:
                info = self.api.recorder_status(self.recorder_id)
                with self._cv:
                    # Keep «starting» until the Pearl confirms (or 10 s pass): a poll that comes
                    # before the recorder has started must not look like «stopped by itself».
                    waiting = (
                        self._start_sent is not None
                        and now - self._start_sent < START_GRACE_S
                        and info.state in (RecordingStatus.STOPPED, RecordingStatus.IDLE)
                    )
                    if not waiting:
                        self.state = info.state
                        if info.state is not RecordingStatus.STARTING:
                            self._start_sent = None
                    self.duration_s = info.duration_s
                    if info.state is RecordingStatus.ERROR:
                        self.last_error = info.description or "Pearl rapporterer feil"
                    fast = self.state is RecordingStatus.STARTING
                    self._next_status = now + (0.5 if fast else STATUS_EVERY_S)
            if now >= self._next_storage:
                storages = self.api.storages()
                with self._cv:
                    self.storages = storages
                    self._next_storage = now + STORAGE_EVERY_S
            with self._cv:
                self._last_ok = now
                if self.state is not RecordingStatus.ERROR:
                    self.last_error = None
        except PearlError as exc:
            with self._cv:
                self.last_error = str(exc)
                self._next_status = now + STATUS_EVERY_S
                if command is not None:
                    self._pending = None  # the session manager times out and tells the user
                    if command == "start" and self.state is RecordingStatus.STARTING:
                        self.state = RecordingStatus.ERROR
            log.warning("Pearl: %s", exc)
