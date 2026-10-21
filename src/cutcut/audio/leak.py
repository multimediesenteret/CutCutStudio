"""Leakage between mics (AU-4, spec 5.3 T1/V1): is this mic active because its own person
talks, or because it hears someone else?

Setup step 5 lets each person talk alone and measures, with :class:`LeakMeasurer`, how much
quieter each voice is on every other mic. The technician approves it into ``baseline.yaml``
(``audio.leak_db``). In operation :class:`LeakDetector` predicts, from the louder mics that
are talking, how loud their leakage on each mic should be. A mic that is not clearly louder
than that prediction is marked ``leak``: the engine then does not count it as talking.

Two people talking at once are both clearly above their predicted leakage, so crosstalk is
never mistaken for leakage. Before setup has measured anything a cautious default is used.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from typing import Final

import numpy as np

from cutcut.audio.dsp import SILENCE_DB
from cutcut.common.ids import MicId

DEFAULT_LEAK_DB: Final = -18.0  # before setup: a small studio with mics 0.5–1 m apart
MARGIN_DB: Final = 6.0  # own voice must be this much louder than the predicted leakage
SMOOTH_MS: Final = 50.0  # level smoothing (power), so a single frame does not flip it
TALKING_DB: Final = -45.0  # a talker this loud is measured in setup step 5
MIN_FRAMES: Final = 100  # 1 s of talking per person before a measurement counts


class LeakDetector:
    def __init__(self, leak_db: Mapping[MicId, Mapping[MicId, float]] | None = None) -> None:
        self.leak_db = {src: dict(row) for src, row in (leak_db or {}).items()}
        self._power: dict[MicId, float] = {}
        self._alpha = 1.0 - math.exp(-10.0 / SMOOTH_MS)

    def gain(self, src: MicId, dst: MicId) -> float:
        return self.leak_db.get(src, {}).get(dst, DEFAULT_LEAK_DB)

    def smoothed_db(self, mic: MicId) -> float:
        p = self._power.get(mic, 0.0)
        return max(SILENCE_DB, 10.0 * math.log10(p)) if p > 0 else SILENCE_DB

    def feed(
        self, level_db: Mapping[MicId, float], active: Mapping[MicId, bool]
    ) -> dict[MicId, bool]:
        """One 10 ms frame → which active mics are only hearing someone else."""
        for mic, db in level_db.items():
            p = 10.0 ** (db / 10.0)
            prev = self._power.get(mic, p)
            self._power[mic] = prev + self._alpha * (p - prev)
        smooth = {mic: self.smoothed_db(mic) for mic in level_db}
        out: dict[MicId, bool] = {}
        for mic in level_db:
            if not active.get(mic, False):
                out[mic] = False
                continue
            predicted = max(
                (
                    smooth[src] + self.gain(src, mic)
                    for src in level_db
                    if src != mic and active.get(src, False) and smooth[src] > smooth[mic]
                ),
                default=None,
            )
            out[mic] = predicted is not None and smooth[mic] <= predicted + MARGIN_DB
        return out


class LeakMeasurer:
    """Setup step 5: «Snakk i mic N». Collects level differences while one person talks."""

    def __init__(self) -> None:
        self._diffs: dict[MicId, dict[MicId, list[float]]] = defaultdict(lambda: defaultdict(list))

    def feed(self, talker: MicId, level_db: Mapping[MicId, float]) -> None:
        own = level_db.get(talker, SILENCE_DB)
        if own < TALKING_DB:
            return  # a breath between words tells nothing about leakage
        for mic, db in level_db.items():
            if mic != talker:
                self._diffs[talker][mic].append(db - own)

    def frames(self, talker: MicId) -> int:
        row = self._diffs.get(talker)
        return max((len(v) for v in row.values()), default=0) if row else 0

    def result(self) -> dict[MicId, dict[MicId, float]]:
        """Median per pair, rounded to 0.5 dB; talkers with under 1 s of speech are left out."""
        out: dict[MicId, dict[MicId, float]] = {}
        for talker, row in self._diffs.items():
            if self.frames(talker) < MIN_FRAMES:
                continue
            out[talker] = {
                mic: float(min(0.0, max(-90.0, round(float(np.median(v)) * 2) / 2)))
                for mic, v in sorted(row.items())
            }
        return out
