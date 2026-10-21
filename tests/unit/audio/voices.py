"""Synthetic voices for the phrase-boundary tests (AU-3). No recordings of people.

A «voice» is a harmonic tone with a pitch contour and a syllable-like amplitude envelope,
the parts of speech that YIN and the energy tracker look at. Deterministic for a given seed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from cutcut.audio.channels import CHANNELS, mic_channel
from cutcut.audio.dsp import Array
from cutcut.common.ids import MicId

SR = 48_000


@dataclass(frozen=True)
class Phrase:
    start_s: float
    seconds: float
    f0: tuple[float, float, float]  # start, before the end, at the end (Hz)
    end_s: float = 0.4  # the last part where the pitch moves to f0[2]
    level_db: float = -20.0
    fade_db: float = 0.0  # level change over the last 0.2 s (negative = trailing off)
    gap: tuple[float, float] | None = None  # a short silence inside the phrase (s from start)


def voice(p: Phrase, rng: np.random.Generator) -> Array:
    n = int(p.seconds * SR)
    t = np.arange(n) / SR
    body = p.seconds - p.end_s
    f0 = np.where(
        t < body,
        p.f0[0] + (p.f0[1] - p.f0[0]) * t / max(body, 1e-9),
        p.f0[1] + (p.f0[2] - p.f0[1]) * (t - body) / p.end_s,
    )
    phase = 2 * np.pi * np.cumsum(f0) / SR
    x = sum(np.sin(k * phase) / k for k in range(1, 12))
    syll = 0.65 + 0.35 * np.sin(2 * np.pi * 4.0 * t) ** 2  # never fully silent: one phrase
    fade = np.where(t > p.seconds - 0.2, (t - (p.seconds - 0.2)) / 0.2, 0.0)
    gain = 10 ** ((p.level_db + p.fade_db * fade) / 20)
    edge = np.minimum(1.0, np.minimum(t, p.seconds - t) / 0.01)  # 10 ms ramps, no clicks
    y = x * syll * edge
    y = y / np.sqrt(np.mean(np.square(y))) * gain
    if p.gap is not None:
        a, b = (int(v * SR) for v in p.gap)
        y[a:b] = 0.0
    y += rng.standard_normal(n) * 10 ** (-60 / 20)  # breath and room
    out: Array = y.astype(np.float32)
    return out


def track(seconds: float, phrases: Sequence[Phrase], mic: MicId = MicId.M1, seed: int = 3) -> Array:
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    out = (rng.standard_normal((n, CHANNELS)) * 10 ** (-70 / 20)).astype(np.float32)
    ch = mic_channel(mic)
    for p in phrases:
        v = voice(p, rng)
        a = int(p.start_s * SR)
        out[a : a + len(v), ch] += v[: n - a]
    return out
