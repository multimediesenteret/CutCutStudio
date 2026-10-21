"""Clocks (ADR-0010).

The engine only uses ``mono_ms()`` for timing rules, so NTP adjustments never change a
decision. ``now()`` is wall-clock time for logs and the UI.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def mono_ms(self) -> int: ...
    def now(self) -> datetime: ...


class SystemClock:
    def __init__(self) -> None:
        self._origin_ns = time.monotonic_ns()

    def mono_ms(self) -> int:
        return (time.monotonic_ns() - self._origin_ns) // 1_000_000

    def now(self) -> datetime:
        return datetime.now(UTC).astimezone()


class FakeClock:
    """Deterministic clock for tests and the simulator. Time only moves when told to."""

    def __init__(self, start: datetime | None = None, mono_ms: int = 0) -> None:
        self._wall = start or datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
        self._mono = mono_ms

    def mono_ms(self) -> int:
        return self._mono

    def now(self) -> datetime:
        return self._wall

    def advance(self, ms: int) -> None:
        if ms < 0:
            raise ValueError("monotonic time cannot go backwards")
        self._mono += ms
        self._wall += timedelta(milliseconds=ms)

    def jump_wall(self, delta: timedelta) -> None:
        """Simulate an NTP correction: wall clock moves, monotonic time does not."""
        self._wall += delta
