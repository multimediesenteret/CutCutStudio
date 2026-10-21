"""The audio-capture loop: backend → analyzer → bus (``audio.frame`` 100 Hz, ``audio.status``
1 Hz). Started by the supervisor; a hang or crash only affects this process, core falls back
to S4 and carries on (ADR-0014)."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from cutcut.audio.analyzer import Analyzer
from cutcut.audio.backend import Backend

log = logging.getLogger(__name__)

Publish = Callable[[str, dict[str, Any]], Awaitable[object]]


def _status(backend: Backend, analyzer: Analyzer, frames: int, ok: bool) -> dict[str, Any]:
    extra = getattr(backend, "status", None)
    detail: dict[str, Any] = extra() if callable(extra) else {}
    running = bool(detail.get("running", ok))
    return {
        "backend": backend.name,
        "vad": analyzer.vad_name,
        "frames": frames,
        "ok": running,
        **detail,
    }


async def run(
    backend: Backend,
    analyzer: Analyzer,
    publish: Publish,
    *,
    realtime: bool = True,
    max_frames: int | None = None,
) -> int:
    """Run until the backend ends (or ``max_frames``). Returns the number of frames sent."""
    sent = 0
    next_at = time.monotonic()
    last_status = -1.0
    while max_frames is None or sent < max_frames:
        block = backend.read()
        now = time.monotonic()
        if now - last_status >= 1.0:  # also while the sound card is down (spec 8.5 H-AUD-1)
            last_status = now
            await publish("audio.status", _status(backend, analyzer, sent, block is not None))
        if block is None:
            if backend.name == "fake":
                break
            await asyncio.sleep(0.002)
            continue
        await publish("audio.frame", analyzer.feed(block))
        sent += 1
        if realtime and backend.name == "fake":
            next_at += 0.010
            await asyncio.sleep(max(0.0, next_at - time.monotonic()))
    return sent
