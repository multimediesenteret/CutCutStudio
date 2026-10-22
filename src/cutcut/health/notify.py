"""Alerts outside the studio (HS-3, spec 8.5 «Varsling», Q29: email to the technician).

* A health issue that has been **red for over a minute** sends one email. When it closes
  (30 s green), a short «OK igjen» follows.
* A red alert that is not a health check, such as a recording that did not start or stopped
  by itself (``H-PRL-1``, ``H-PRL-2``), sends at once: the person cannot wait a minute.
* At most ``max_per_hour`` emails an hour; the rest wait in a small outbox, oldest dropped.

Sending happens in a worker thread from the health loop, outside the engine's tick, so a slow
or broken mail relay never touches the cutting (spec 8.5: «Kjøres utenfor sanntidssløyfen»).
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

from cutcut.health.engine import HealthEvent

log = logging.getLogger(__name__)

OUTBOX: Final = 20
RETRY_S: Final = 60.0
REPEAT_S: Final = 600.0  # the same non-health alert again within 10 min: no new email

RUNBOOKS: Final = {
    "H-AUD": "h-aud-1-ingen-lyd.md",
    "H-PROC-touch": "h-proc-touch-touch-er-svart.md",
    "H-PRL": "h-prl-opptak-startet-ikke.md",
    "H-CAM": "h-cam-kamera-beveger-seg-ikke.md",
}


def runbook(check: str) -> str | None:
    for prefix, name in RUNBOOKS.items():
        if check.startswith(prefix):
            return f"docs/runbooks/{name}"
    return None


@dataclass
class Mail:
    subject: str
    body: str


@dataclass
class Notifier:
    send: Callable[[list[str], str, str], None]  # blocking; runs in a worker thread
    to: Callable[[], list[str]]
    studio: str
    mono_s: Callable[[], float]
    now: Callable[[], datetime]
    red_after_s: float = 60.0
    max_per_hour: int = 10
    on: Callable[[], bool] = lambda: True  # off: nothing is queued, so nothing piles up
    sent: int = 0
    dropped: int = 0
    last_sent: datetime | None = None
    last_error: str | None = None
    _red: dict[str, tuple[float, str]] = field(default_factory=dict)  # id → (since, message)
    _mailed: set[str] = field(default_factory=set)
    _alerted: dict[str, float] = field(default_factory=dict)
    _outbox: deque[Mail] = field(default_factory=deque)
    _times: deque[float] = field(default_factory=deque)
    _retry_at: float = 0.0

    # --- input -------------------------------------------------------------------------

    def on_health(self, ev: HealthEvent) -> None:
        r = ev.result
        if ev.kind == "resolved":
            self._red.pop(r.id, None)
            if r.id in self._mailed:
                self._mailed.discard(r.id)
                mins = ev.duration_s / 60
                self._queue(
                    f"OK igjen: {r.id}",
                    f"{r.id} er grønn igjen etter {mins:.0f} min.\n\n{r.message}",
                )
            return
        if r.status == "red":
            since = self._red.get(r.id, (self.mono_s(), r.message))[0]
            self._red[r.id] = (since, r.message)
        else:
            self._red.pop(r.id, None)

    def on_alert(self, code: str, message: str) -> None:
        """A red alert that is not a health check (recording failed): mail at once."""
        t = self.mono_s()
        last = self._alerted.get(code)
        if last is not None and t - last < REPEAT_S:
            return
        self._alerted[code] = t
        self._queue(f"Rødt: {message}", self._body(code, message))

    # --- output ------------------------------------------------------------------------

    def _body(self, check: str, message: str) -> str:
        lines = [
            f"Studio: {self.studio}",
            f"Sjekk: {check}",
            f"Tid: {self.now().astimezone():%Y-%m-%d %H:%M}",
            "",
            message,
            "",
            "Opptaket på Pearl går videre; CutCut stopper det aldri selv (I7).",
            "Se teknikervinduet → Helse.",
        ]
        rb = runbook(check)
        if rb:
            lines.append(f"Runbook: {rb}")
        return "\n".join(lines)

    def _queue(self, subject: str, body: str) -> None:
        if not self.on():
            return
        self._outbox.append(Mail(f"[CutCut {self.studio}] {subject}", body))
        while len(self._outbox) > OUTBOX:
            self._outbox.popleft()
            self.dropped += 1

    def step(self) -> None:
        """Health issues that have now been red long enough get their email."""
        t = self.mono_s()
        for cid, (since, message) in self._red.items():
            if cid not in self._mailed and t - since >= self.red_after_s:
                self._mailed.add(cid)
                self._queue(f"Rødt: {cid}", self._body(cid, message))

    async def flush(self) -> None:
        if not self.on():
            self._outbox.clear()  # turned off: old news is not sent the day it is turned on
            return
        to = self.to()
        t = self.mono_s()
        if not to or t < self._retry_at:
            return
        while self._outbox:
            while self._times and t - self._times[0] >= 3600:
                self._times.popleft()
            if len(self._times) >= self.max_per_hour:
                return  # wait; the outbox keeps the newest
            mail = self._outbox[0]
            try:
                await asyncio.to_thread(self.send, to, mail.subject, mail.body)
            except Exception as e:
                self.last_error = str(e) or type(e).__name__
                self._retry_at = t + RETRY_S
                log.warning("Varsel på e-post ble ikke sendt: %s", self.last_error)
                return
            self._outbox.popleft()
            self._times.append(t)
            self.sent += 1
            self.last_sent, self.last_error = self.now(), None
            log.info("Varsel sendt på e-post: %s", mail.subject)

    async def tick(self) -> None:
        self.step()
        await self.flush()
