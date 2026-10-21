"""Keeps the studio's processes running (SO-1, spec 9.1).

* Starts each process; when one exits, starts it again after a growing pause
  (1, 2, 5, 10, 30 s). After 60 s of good running the pause goes back to 1 s.
* A process that runs but does not answer (3 failed health checks in a row) is killed and
  started again – a hang is treated like a crash.
* More than 5 restarts of one process in 10 minutes is reported (``H-PROC-1``), so a
  technician hears about a process that keeps falling over even though the studio works.

Deliberately simple and with no knowledge of the studio: no rules, only processes.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from cutcut.supervisor.orphans import bind_to_us, linux_preexec

log = logging.getLogger(__name__)

BACKOFF_S: Final = (1.0, 2.0, 5.0, 10.0, 30.0)
STABLE_S: Final = 60.0
HEALTH_FAILS: Final = 3
FLAP_COUNT: Final = 5
FLAP_WINDOW_S: Final = 600.0
STOP_GRACE_S: Final = 5.0

Health = Callable[[], bool]


@dataclass(frozen=True)
class ProcessSpec:
    name: str
    args: Sequence[str] | Callable[[], Sequence[str]]  # a callable is evaluated at each start
    cwd: Path | None = None
    env: dict[str, str] = field(default_factory=dict)
    health: Health | None = None  # None: «running» is enough
    health_every_s: float = 2.0


@dataclass
class ProcessState:
    spec: ProcessSpec
    proc: subprocess.Popen[bytes] | None = None
    started_at: float | None = None
    next_start: float = 0.0
    attempt: int = 0
    health_fails: int = 0
    next_health: float = 0.0
    restarts: deque[float] = field(default_factory=deque)
    last_exit: int | None = None
    last_reason: str | None = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None


class Supervisor:
    def __init__(
        self,
        specs: Sequence[ProcessSpec],
        *,
        clock: Callable[[], float] = time.monotonic,
        on_flap: Callable[[str, int], None] | None = None,
    ) -> None:
        self.states = {s.name: ProcessState(s) for s in specs}
        self.clock = clock
        self.on_flap = on_flap

    # -- one round ------------------------------------------------------------------------

    def step(self) -> None:
        now = self.clock()
        for st in self.states.values():
            if st.proc is not None and st.proc.poll() is not None:
                self._exited(st, now, f"avsluttet med kode {st.proc.returncode}")
            if st.proc is None and now >= st.next_start:
                self._start(st, now)
            elif st.running:
                if st.started_at is not None and now - st.started_at >= STABLE_S:
                    st.attempt = 0
                self._check_health(st, now)

    def _start(self, st: ProcessState, now: float) -> None:
        spec = st.spec
        args = list(spec.args() if callable(spec.args) else spec.args)
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP  # so a stop signal reaches only it
        try:
            st.proc = subprocess.Popen(  # noqa: S603 - our own fixed command lines
                args,
                cwd=spec.cwd,
                env={**os.environ, **spec.env},
                creationflags=flags,
                start_new_session=sys.platform != "win32",
                preexec_fn=linux_preexec(),  # only sets PDEATHSIG; no locks taken
            )
        except OSError as exc:
            log.error("%s: kunne ikke startes: %s", spec.name, exc)
            st.last_reason = f"kunne ikke startes: {exc}"
            self._schedule(st, now)
            return
        bind_to_us(st.proc)
        st.started_at = now
        st.health_fails = 0
        st.next_health = now + max(spec.health_every_s, 5.0)  # give it time to come up
        log.info("%s startet (pid %s)", spec.name, st.proc.pid)

    def _exited(self, st: ProcessState, now: float, reason: str) -> None:
        st.last_exit = st.proc.returncode if st.proc is not None else None
        st.last_reason = reason
        st.proc = None
        log.warning("%s: %s", st.spec.name, reason)
        st.restarts.append(now)
        while st.restarts and now - st.restarts[0] > FLAP_WINDOW_S:
            st.restarts.popleft()
        if len(st.restarts) > FLAP_COUNT and self.on_flap is not None:
            self.on_flap(st.spec.name, len(st.restarts))
        self._schedule(st, now)

    def _schedule(self, st: ProcessState, now: float) -> None:
        pause = BACKOFF_S[min(st.attempt, len(BACKOFF_S) - 1)]
        st.attempt += 1
        st.next_start = now + pause

    def _check_health(self, st: ProcessState, now: float) -> None:
        if st.spec.health is None or now < st.next_health:
            return
        st.next_health = now + st.spec.health_every_s
        try:
            ok = st.spec.health()
        except Exception:
            ok = False
        st.health_fails = 0 if ok else st.health_fails + 1
        if st.health_fails >= HEALTH_FAILS:
            log.error("%s svarer ikke; stoppes og startes på nytt", st.spec.name)
            self._kill(st)
            self._exited(st, now, "svarte ikke (hang)")

    # -- stopping ---------------------------------------------------------------------------

    def _kill(self, st: ProcessState) -> None:
        proc = st.proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if sys.platform == "win32":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=STOP_GRACE_S)
        except (subprocess.TimeoutExpired, OSError):
            proc.kill()
            proc.wait(timeout=STOP_GRACE_S)

    def stop_all(self) -> None:
        for st in self.states.values():
            self._kill(st)
            st.proc = None

    # -- reporting --------------------------------------------------------------------------

    def status(self) -> list[dict[str, object]]:
        now = self.clock()
        return [
            {
                "name": name,
                "running": st.running,
                "pid": st.proc.pid if st.running and st.proc else None,
                "uptime_s": round(now - st.started_at) if st.running and st.started_at else 0,
                "restarts_10min": len([t for t in st.restarts if now - t <= FLAP_WINDOW_S]),
                "last_exit": st.last_exit,
                "last_reason": st.last_reason,
            }
            for name, st in self.states.items()
        ]

    def run(self, report: Callable[[list[dict[str, object]]], None] | None = None) -> None:
        """Run until stopped. ``report`` gets the status every 2 s (to core).

        A stop request (Ctrl+C, SIGTERM from a service manager, Ctrl+Break on Windows) stops
        the children before the supervisor ends.
        """

        def stop(*_: object) -> None:
            raise KeyboardInterrupt

        for name in ("SIGTERM", "SIGBREAK"):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), stop)
        last = 0.0
        try:
            while True:
                self.step()
                if report is not None and self.clock() - last >= 2.0:
                    last = self.clock()
                    try:
                        report(self.status())
                    except Exception as exc:  # core may be restarting
                        log.debug("status ble ikke levert: %s", exc)
                time.sleep(0.5)
        finally:
            self.stop_all()
