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
from collections.abc import Callable, Mapping
from typing import Final

import numpy as np

from cutcut.audio.dsp import SILENCE_DB
from cutcut.common.ids import MicId

DEFAULT_LEAK_DB: Final = -18.0  # before setup: a small studio with mics 0.5–1 m apart
MARGIN_DB: Final = 6.0  # own voice must be this much louder than the predicted leakage
SMOOTH_MS: Final = 50.0  # level smoothing (power), so a single frame does not flip it
TALKING_DB: Final = -45.0  # a talker this loud is measured in setup step 5
MIN_FRAMES: Final = 100  # 1 s of talking per person before a measurement counts
# P13: session adaptation
SOLO_DB: Final = 10.0  # the talker is this much louder than every other mic: talking alone
FLOOR_DB: Final = -70.0  # below this a mic hears only the room
ADAPT_TAU_S: Final = 30.0  # smoothing, in seconds of solo speech
ADAPT_LIMIT_DB: Final = 6.0  # never further than this from setup's matrix


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
        return self.decide(active, self.gain)

    def smoothed(self) -> dict[MicId, float]:
        return {mic: self.smoothed_db(mic) for mic in self._power}

    def decide(
        self, active: Mapping[MicId, bool], gain: Callable[[MicId, MicId], float]
    ) -> dict[MicId, bool]:
        """Which active mics are explained by a louder active mic through ``gain`` (+ margin),
        from the levels of the last :meth:`feed`."""
        smooth = self.smoothed()
        out: dict[MicId, bool] = {}
        for mic in smooth:
            if not active.get(mic, False):
                out[mic] = False
                continue
            predicted = max(
                (
                    smooth[src] + gain(src, mic)
                    for src in smooth
                    if src != mic and active.get(src, False) and smooth[src] > smooth[mic]
                ),
                default=None,
            )
            out[mic] = predicted is not None and smooth[mic] <= predicted + MARGIN_DB
        return out


class AdaptiveLeak:
    """P13: the leakage as it is in this session. People are new each time and move the mics,
    so the matrix from setup step 5 is a starting point. While one person clearly talks alone,
    the leakage from their mic to each other mic is measured and smoothed over about
    ``ADAPT_TAU_S`` of such speech, and kept within ``ADAPT_LIMIT_DB`` of the starting point,
    so a wrong measurement can never do much harm. :meth:`reset` at every new session.

    Runs off, in shadow (published as ``leak_adapt`` next to ``leak``, for comparison) or on
    (``leak`` uses it), set with ``audio.config`` (``adapt``) from the switch ``audio_adapt``."""

    def __init__(self, base: LeakDetector) -> None:
        self.base = base
        self.adapted: dict[MicId, dict[MicId, float]] = {}
        self.solo_frames: dict[MicId, int] = {}
        self._alpha = 1.0 - math.exp(-10.0 / (ADAPT_TAU_S * 1000.0))

    def reset(self) -> None:
        self.adapted, self.solo_frames = {}, {}

    def gain(self, src: MicId, dst: MicId) -> float:
        row = self.adapted.get(src)
        if row is not None and dst in row:
            return row[dst]
        return self.base.gain(src, dst)

    def observe(self, smooth: Mapping[MicId, float]) -> MicId | None:
        """One frame of smoothed levels. Returns the solo talker when one was measured."""
        if len(smooth) < 2:
            return None
        src = max(smooth, key=lambda m: smooth[m])
        top = smooth[src]
        rest = max(v for m, v in smooth.items() if m != src)
        if top < TALKING_DB or top - rest < SOLO_DB:
            return None
        self.solo_frames[src] = self.solo_frames.get(src, 0) + 1
        row = self.adapted.setdefault(src, {})
        for dst, db in smooth.items():
            if dst == src or db <= FLOOR_DB:
                continue  # at the noise floor the leakage is not measurable
            start = self.base.gain(src, dst)
            prev = row.get(dst, start)
            new = prev + self._alpha * ((db - top) - prev)
            row[dst] = min(start + ADAPT_LIMIT_DB, max(start - ADAPT_LIMIT_DB, new))
        return src

    def matrix(self) -> dict[MicId, dict[MicId, float]]:
        return {
            src: {dst: round(v, 1) for dst, v in sorted(row.items())}
            for src, row in sorted(self.adapted.items())
        }


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

    def reset(self, talker: MicId) -> None:
        self._diffs.pop(talker, None)

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
