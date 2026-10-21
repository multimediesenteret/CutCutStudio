"""``S6``: is this mic in the RØDECaster's main mix? (AU-4, spec 5.7, D-035, Q24)

The multitrack tracks are recorded before the fader (pre-fader). If someone's fader is down
or muted, their own track still has their voice, but the broadcast does not: the engine must
not cut to a person nobody can hear. The main mix (channels 1–2) is compared with each mic.

The comparison is on the level envelopes (10 ms dB values over the last 0.5 s), not the
waveforms, so the mixer's EQ, compressor and a few ms of delay do not matter. When a person
talks and is in the mix, the main mix rises and falls with their syllables (correlation
near 1). When muted, it does not (near 0). A mic that has been out of step for 0.5 s is
reported ``in_main_mix = false``; one good window brings it back at once. Before the main
mix has carried any sound at all (not routed, or the studio is silent) nothing is judged.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Final

import numpy as np

WINDOW: Final = 50  # frames (0.5 s)
MIN_FRAMES: Final = 30
OUT_CORR: Final = 0.3
IN_CORR: Final = 0.5
OUT_AFTER_MS: Final = 500
MIN_SWING_DB: Final = 1.5  # the mic's envelope must move to judge anything
MAIN_ALIVE_DB: Final = -50.0
MAIN_ALIVE_MS: Final = 600_000  # the main mix carried sound in the last 10 minutes


@dataclass
class _Mic:
    env: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=WINDOW))
    low_ms: int = 0
    in_mix: bool = True


class MainMixWatch:
    def __init__(self) -> None:
        self._mics: dict[str, _Mic] = {}
        self._alive_ms = 0  # time left in which the main mix counts as carrying sound

    def feed(
        self, main_db: float, mic_db: dict[str, float], active: dict[str, bool]
    ) -> dict[str, bool]:
        if main_db >= MAIN_ALIVE_DB:
            self._alive_ms = MAIN_ALIVE_MS
        else:
            self._alive_ms = max(0, self._alive_ms - 10)
        out: dict[str, bool] = {}
        for mic, db in mic_db.items():
            m = self._mics.setdefault(mic, _Mic())
            if not active.get(mic, False):
                m.env.clear()  # judge each phrase on its own; keep the verdict meanwhile
                out[mic] = m.in_mix
                continue
            m.env.append((db, main_db))
            if self._alive_ms == 0 or len(m.env) < MIN_FRAMES:
                out[mic] = m.in_mix if self._alive_ms else True
                continue
            corr = self._corr(m.env)
            if corr is None:
                pass
            elif corr >= IN_CORR:
                m.in_mix, m.low_ms = True, 0
            elif corr < OUT_CORR:
                m.low_ms += 10
                if m.low_ms >= OUT_AFTER_MS:
                    m.in_mix = False
            out[mic] = m.in_mix
        return out

    @staticmethod
    def _corr(env: deque[tuple[float, float]]) -> float | None:
        a = np.array(env, dtype=np.float64)
        mic, main = a[:, 0], a[:, 1]
        if mic.std() < MIN_SWING_DB / 2:
            return None  # a steady tone tells nothing
        if main.std() < 0.25:
            return 0.0  # the main mix does not move at all while the mic does
        return float(np.corrcoef(mic, main)[0, 1])
