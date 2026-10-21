"""Runs the health checks, each on its own interval, and keeps one issue per problem.

* Every check runs in its own task with a timeout, so a check that hangs or throws is
  reported yellow («sjekken virker ikke») and never delays the engine's tick or crashes core.
* **Hysteresis (8.5):** a problem opens an issue at once. It is only closed when the check
  has been green for 30 s, so a flapping device gives one issue, not a stream of them.
* **Logged once:** each issue gives one event when it opens, one if it gets worse or better
  while open (yellow ↔ red), and one when it closes – with start and end.

Checks never press buttons or move anything; those live in the setup wizard only.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Literal, Protocol

from cutcut.health.model import RANK, CheckLevel, CheckResult, Status

log = logging.getLogger(__name__)

RESOLVE_AFTER_S: Final = 30.0
DEFAULT_TIMEOUT_S: Final = 3.0


class HealthCheck(Protocol):
    id: str
    interval_s: float
    level: CheckLevel
    timeout_s: float

    async def run(self) -> CheckResult: ...


@dataclass
class FuncCheck:
    """A check from a function. Sync functions must be cheap (read state, no I/O); anything
    that waits on the network should be ``async`` or use ``asyncio.to_thread``."""

    id: str
    interval_s: float
    fn: Callable[[], CheckResult | Awaitable[CheckResult]]
    level: CheckLevel = "connected"
    timeout_s: float = DEFAULT_TIMEOUT_S

    async def run(self) -> CheckResult:
        out = self.fn()
        if inspect.isawaitable(out):
            return await out
        return out


@dataclass(frozen=True)
class HealthEvent:
    kind: Literal["opened", "changed", "resolved"]
    result: CheckResult
    since: datetime  # when the issue opened
    duration_s: float = 0.0  # for «resolved»


@dataclass
class _State:
    check: HealthCheck
    next_run: float = 0.0
    last: CheckResult | None = None
    issue_since: datetime | None = None
    issue_mono: float = 0.0
    issue_status: Status | None = None
    green_since: float | None = None
    running: bool = False


@dataclass
class HealthEngine:
    checks: Sequence[HealthCheck]
    mono_s: Callable[[], float]  # monotonic seconds
    now: Callable[[], datetime]
    on_event: Callable[[HealthEvent], None] | None = None
    resolve_after_s: float = RESOLVE_AFTER_S
    _states: dict[str, _State] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for c in self.checks:
            self.add(c)

    def add(self, check: HealthCheck) -> None:
        """Add a check (core adds the device checks for the equipment it connects)."""
        if check.id in self._states:
            raise ValueError(f"sjekk-ID {check.id} finnes to ganger")
        self._states[check.id] = _State(check)

    # -- running ---------------------------------------------------------------------------

    async def step(self) -> None:
        """Run every check that is due, concurrently, and wait for them (with timeouts)."""
        now = self.mono_s()
        due = [s for s in self._states.values() if now >= s.next_run and not s.running]
        for s in due:
            s.next_run = now + s.check.interval_s
        await asyncio.gather(*(self._run(s) for s in due))

    async def run_all(self) -> list[CheckResult]:
        """The whole catalogue now (start-up and the morning check, HS-4)."""
        await asyncio.gather(*(self._run(s) for s in self._states.values() if not s.running))
        return self.results()

    async def loop(self, every_s: float = 0.25) -> None:
        while True:
            try:
                await self.step()
            except Exception:  # never let health take core down
                log.exception("helsesjekkene feilet")
            await asyncio.sleep(every_s)

    async def _run(self, s: _State) -> None:
        s.running = True
        try:
            result = await asyncio.wait_for(s.check.run(), timeout=s.check.timeout_s)
            if result.id != s.check.id:
                raise ValueError(f"svarte med ID {result.id}")
        except TimeoutError:
            result = self._broken(s.check, f"svarte ikke innen {s.check.timeout_s:g} s")
        except Exception as exc:
            log.warning("%s: sjekken feilet: %s", s.check.id, exc)
            result = self._broken(s.check, type(exc).__name__)
        finally:
            s.running = False
        self.record(result)

    def _broken(self, check: HealthCheck, why: str) -> CheckResult:
        return CheckResult(
            id=check.id,
            status="yellow",
            value="sjekken virker ikke",
            message=f"Sjekken {check.id} virker ikke ({why}).",
            ts=self.now(),
            level=check.level,
        )

    # -- hysteresis --------------------------------------------------------------------------

    def record(self, result: CheckResult) -> None:
        s = self._states[result.id]
        mono = self.mono_s()
        if result.status != "green":
            s.green_since = None
            if s.issue_since is None:
                s.issue_since, s.issue_mono, s.issue_status = result.ts, mono, result.status
                self._emit(HealthEvent("opened", result, result.ts))
            elif result.status != s.issue_status:
                s.issue_status = result.status
                self._emit(HealthEvent("changed", result, s.issue_since))
        elif s.issue_since is not None:
            if s.green_since is None:
                s.green_since = mono
            if mono - s.green_since >= self.resolve_after_s:
                self._emit(
                    HealthEvent("resolved", result, s.issue_since, round(mono - s.issue_mono, 1))
                )
                s.issue_since, s.issue_status, s.green_since = None, None, None
        s.last = result.model_copy(update={"since": s.issue_since}) if s.issue_since else result

    def _emit(self, ev: HealthEvent) -> None:
        r = ev.result
        if ev.kind == "resolved":
            log.info("%s løst etter %s s", r.id, ev.duration_s, extra={"check": r.id})
        else:
            log.warning("%s %s: %s", r.id, r.status, r.message, extra={"check": r.id})
        if self.on_event is not None:
            try:
                self.on_event(ev)
            except Exception:
                log.exception("varsel for %s feilet", r.id)

    # -- reading -----------------------------------------------------------------------------

    def results(self) -> list[CheckResult]:
        return [s.last for s in self._states.values() if s.last is not None]

    def overall(self) -> Status:
        """Worst open issue (an issue still waiting out its 30 s green counts as open)."""
        worst: Status = "green"
        for s in self._states.values():
            if s.issue_status is not None and RANK[s.issue_status] > RANK[worst]:
                worst = s.issue_status
        return worst
