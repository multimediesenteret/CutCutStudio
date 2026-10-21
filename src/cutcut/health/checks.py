"""The health catalogue (spec 8.5), built from small getters so it runs the same in the
studio and in the simulator. HS-1 has the audio stream; HS-2 adds the rest one device at a
time.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from cutcut.health.engine import FuncCheck
from cutcut.health.model import CheckResult

AUDIO_RED_MS = 2_000  # S4: two seconds without measurements (spec 5.7)


def audio_stream(age_ms: Callable[[], int | None], now: Callable[[], datetime]) -> FuncCheck:
    """``H-AUD-1``: measurements from audio-capture arrive (the ASIO stream is alive)."""

    def run() -> CheckResult:
        age = age_ms()
        if age is None:
            status, value, msg = "red", "ingen lyd", "Ingen lyd fra audio-capture ennå."
        elif age > AUDIO_RED_MS:
            status, value = "red", f"{age / 1000:.1f} s siden"
            msg = "Lyden fra RØDECaster har stoppet. Motoren klipper ikke på lyd (S4)."
        else:
            status, value, msg = "green", f"{age} ms", "Lyden kommer jevnt."
        return CheckResult(
            id="H-AUD-1",
            status=status,  # type: ignore[arg-type]
            value=value,
            expected=f"under {AUDIO_RED_MS} ms",
            message=msg,
            ts=now(),
            # The touch screen already hears about lost audio from the engine (S4), at once
            # and only while it lasts; this check is for the technician.
        )

    return FuncCheck("H-AUD-1", 1.0, run)
