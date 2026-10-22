"""Turns the engine's intents into Companion button presses (ADR-0005, ADR-0009, spec 7.1).

The engine ticks every 30 ms and must never wait for a device, so ``submit`` only queues.
A worker thread sends one command at a time:

* **Latest wins:** a new preview (row 0 or a layout macro) replaces one that is not sent yet.
* **Variables** (``regi_*``) are coalesced per name and sent at most 5 times a second.
* **Circuit breaker:** 3 failures in a row open it for 10 s and Companion counts as down.
* **S5 reserve cut:** while Companion is down, a TAKE becomes a direct cut of the source that
  was meant to be on preview, sent through the fallback (atem-bridge). Layouts are not
  possible then; the engine is told via ``status().ok`` (``companion_ok``).

Direct cuts and «Kun lyd» use the operator page (11) when the button is mapped, otherwise the
fallback. Nothing here decides what to cut; it only carries out what the engine decided (I3).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final, Protocol

from cutcut.common.ids import RuleId, SourceId
from cutcut.common.models.site import CompanionButton, CompanionMap
from cutcut.core.intents import (
    DirectCut,
    Intent,
    PrepareLayout,
    SetCompanionVariable,
    SetPreview,
    ShowAudioOnly,
    Take,
)
from cutcut.devices.companion.client import CompanionError

log = logging.getLogger(__name__)

FAILS_TO_OPEN: Final = 3
OPEN_S: Final = 10.0
VAR_INTERVAL_S: Final = 0.2


class CompanionApi(Protocol):
    def press(self, page: int, row: int, col: int) -> None: ...
    def set_var(self, name: str, value: str) -> None: ...


class Fallback(Protocol):
    def submit(self, intent: Intent) -> None: ...


@dataclass(frozen=True)
class _Press:
    page: int
    button: CompanionButton
    label: str
    is_preview: bool = False


@dataclass
class CompanionStatus:
    ok: bool = True
    sent: int = 0
    failed: int = 0
    dropped: int = 0
    reserve_cuts: int = 0
    last_error: str | None = None
    open_until: float = 0.0
    queue: int = 0


@dataclass
class CompanionExecutor:
    api: CompanionApi
    cmap: CompanionMap
    engine_page: int = 10
    operator_page: int = 11
    fallback: Fallback | None = None
    clock: Callable[[], float] = time.monotonic
    start_thread: bool = True

    _queue: deque[_Press] = field(init=False, default_factory=deque)
    _vars: dict[str, str] = field(init=False, default_factory=dict)
    _cv: threading.Condition = field(init=False, default_factory=threading.Condition)
    _status: CompanionStatus = field(init=False, default_factory=CompanionStatus)
    _fails: int = field(init=False, default=0)
    _preview_target: SourceId | None = field(init=False, default=None)
    _stop: bool = field(init=False, default=False)
    _last_var_s: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self._thread: threading.Thread | None = None
        if self.start_thread:
            self._thread = threading.Thread(target=self._run, name="companion", daemon=True)
            self._thread.start()

    # -- engine side (never blocks) -------------------------------------------------------

    def submit(self, intent: Intent) -> None:
        with self._cv:
            self._submit(intent)
            self._cv.notify()

    def _submit(self, intent: Intent) -> None:
        down = self._is_open()
        match intent:
            case SetPreview(source=source):
                self._preview_target = source
                button = self.cmap.preview.get(source)
                if button is None:
                    self._drop(f"ingen preview-knapp for {source}")
                elif not down:
                    self._replace_preview(
                        _Press(self.engine_page, button, f"preview {source}", True)
                    )
            case PrepareLayout(shot=shot):
                self._preview_target = None  # layouts cannot be cut directly (S5)
                button = self.cmap.layouts.get(shot)
                if button is None or down:
                    self._drop(f"layout {shot} ikke mulig")
                else:
                    self._replace_preview(_Press(self.engine_page, button, f"layout {shot}", True))
            case Take(transition=transition):
                if down:
                    self._reserve_cut()
                else:
                    button = self.cmap.take_cut if transition == "cut" else self.cmap.take_mix
                    self._queue.append(_Press(self.engine_page, button, f"take {transition}"))
            case DirectCut(source=source):
                button = self.cmap.operator_direct.get(source)
                if button is not None and not down:
                    self._queue.append(_Press(self.operator_page, button, f"direkte {source}"))
                else:
                    self._to_fallback(intent)
            case ShowAudioOnly():
                button = self.cmap.operator_audio_only
                if button is not None and not down:
                    self._queue.append(_Press(self.operator_page, button, "kun lyd"))
                else:
                    self._to_fallback(intent)
            case SetCompanionVariable(name=name, value=value):
                self._vars[name] = value

    def _replace_preview(self, press: _Press) -> None:
        """Latest wins – but only after the last queued TAKE or cut, so a TAKE always takes
        the preview that was set before it."""
        items = list(self._queue)
        last_other = max((i for i, p in enumerate(items) if not p.is_preview), default=-1)
        kept = items[: last_other + 1] + [p for p in items[last_other + 1 :] if not p.is_preview]
        if len(kept) != len(items):
            self._status.dropped += 1  # superseded before it was sent
        self._queue.clear()
        self._queue.extend(kept)
        self._queue.append(press)

    def _reserve_cut(self) -> None:
        if self._preview_target is None:
            self._drop("reservekutt uten kilde")
            return
        self._status.reserve_cuts += 1
        log.warning(
            "%s: Companion nede, reservekutt til %s via atem-bridge",
            RuleId.S5.value,
            self._preview_target,
        )
        self._to_fallback(DirectCut(self._preview_target))

    def _to_fallback(self, intent: Intent) -> None:
        if self.fallback is None:
            self._drop(f"ingen reservevei for {type(intent).__name__}")
        else:
            self.fallback.submit(intent)

    def _drop(self, why: str) -> None:
        self._status.dropped += 1
        log.info("Companion: %s", why)

    def _is_open(self) -> bool:
        return self.clock() < self._status.open_until

    def status(self) -> CompanionStatus:
        with self._cv:
            s = self._status
            return CompanionStatus(
                ok=not self._is_open(),
                sent=s.sent,
                failed=s.failed,
                dropped=s.dropped,
                reserve_cuts=s.reserve_cuts,
                last_error=s.last_error,
                open_until=s.open_until,
                queue=len(self._queue) + len(self._vars),
            )

    # -- worker ---------------------------------------------------------------------------

    def close(self) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while True:
            with self._cv:
                while not self._stop and not self._queue and not self._vars:
                    self._cv.wait(timeout=0.5)
                if self._stop:
                    return
            self.step()

    def step(self) -> bool:
        """Send at most one command. Public so tests can drive it without a thread."""
        with self._cv:
            if self._is_open():
                # Nothing is sent while open; keep only the freshest preview and variables.
                return False
            press = self._queue.popleft() if self._queue else None
            var: tuple[str, str] | None = None
            if press is None and self._vars and self.clock() - self._last_var_s >= VAR_INTERVAL_S:
                name = next(iter(self._vars))
                var = (name, self._vars.pop(name))
                self._last_var_s = self.clock()
        if press is None and var is None:
            return False
        try:
            if press is not None:
                self.api.press(press.page, press.button.row, press.button.col)
            elif var is not None:
                self.api.set_var(*var)
        except CompanionError as exc:
            self._failed(str(exc))
            return True
        with self._cv:
            self._fails = 0
            self._status.sent += 1
        return True

    def _failed(self, error: str) -> None:
        with self._cv:
            self._fails += 1
            self._status.failed += 1
            self._status.last_error = error
            if self._fails >= FAILS_TO_OPEN:
                self._status.open_until = self.clock() + OPEN_S
                self._fails = 0
                self._queue.clear()  # stale presses must not fire when Companion is back
                log.error("Companion nede (%s): reservekutt i %.0f s (S5)", error, OPEN_S)
