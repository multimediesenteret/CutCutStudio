"""Phrase boundaries per mic (AU-3, spec 5.10): pause, energy fall and falling pitch.

Runs on the 10 ms frames, after the VAD. The engine reads three fields:

* ``pitch_falling`` – the pitch fell towards the end of the phrase that just ended (a
  statement ending, not a question or a hesitation). Used by ``K2``: a cut may come after
  only 150 ms of pause instead of 250 ms.
* ``energy_fall`` – the voice trailed off: the last 150 ms of the phrase were clearly below
  the phrase's own level.
* ``phrase_end`` – this pause is a phrase boundary: 250 ms of pause, or 150 ms when the pitch
  fell or the voice trailed off. Held for the whole pause, cleared when the mic talks again.

Pitch is found with YIN (de Cheveigné & Kawahara 2002) on 16 kHz audio: 25 ms window,
64–500 Hz, only while the mic is active and loud enough, so the analysis costs nothing on
silent mics. Everything is deterministic: the same audio always gives the same frames.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Final

import numpy as np

from cutcut.audio.dsp import SILENCE_DB, Array

SR16: Final = 16_000
YIN_W: Final = 400  # 25 ms window
TAU_MIN: Final = SR16 // 500  # 500 Hz
TAU_MAX: Final = SR16 // 64  # 64 Hz
YIN_THRESHOLD: Final = 0.15
BUF: Final = YIN_W + TAU_MAX + 1

PHRASE_PAUSE_MS: Final = 250  # spec 5.10 K2: plain pause
SHORT_PAUSE_MS: Final = 150  # with falling pitch or energy fall
FALL_SEMITONES: Final = 1.5  # end of phrase at least this far below the part before it
ENERGY_FALL_DB: Final = 6.0
TAIL_MS: Final = 250  # «end of the phrase» for pitch
BEFORE_MS: Final = 500  # compared with the 500 ms before that
ENERGY_TAIL_MS: Final = 150
MIN_VOICED: Final = 5  # pitch frames needed in each part
VOICED_BELOW_PEAK_DB: Final = 18.0  # quieter frames are ignored for pitch (VAD hangover)
HISTORY_MS: Final = 2_000


def yin(x: Array, sr: int = SR16) -> float | None:
    """Fundamental frequency in Hz of the newest ``YIN_W + TAU_MAX`` samples, or None."""
    if len(x) < YIN_W + TAU_MAX:
        return None
    x = x[-(YIN_W + TAU_MAX) :].astype(np.float64)
    n = len(x)
    size = 1 << (n + YIN_W - 1).bit_length()
    # r(tau) = sum_j x[j] * x[j + tau], j < W  (cross-correlation via FFT)
    spec = np.fft.rfft(x, size) * np.conj(np.fft.rfft(x[:YIN_W], size))
    r = np.fft.irfft(spec, size)[: TAU_MAX + 1]
    sq = np.concatenate([[0.0], np.cumsum(x * x)])
    taus = np.arange(TAU_MAX + 1)
    e0 = sq[YIN_W]
    et = sq[taus + YIN_W] - sq[taus]
    d = np.maximum(e0 + et - 2.0 * r, 0.0)
    d[0] = 0.0
    cum = np.cumsum(d[1:])
    dn = np.ones_like(d)
    with np.errstate(divide="ignore", invalid="ignore"):
        dn[1:] = np.where(cum > 0, d[1:] * taus[1:] / cum, 1.0)
    below = np.nonzero(dn[TAU_MIN : TAU_MAX + 1] < YIN_THRESHOLD)[0]
    if below.size == 0:
        return None
    tau = int(below[0]) + TAU_MIN
    while tau + 1 <= TAU_MAX and dn[tau + 1] < dn[tau]:
        tau += 1
    if TAU_MIN < tau < TAU_MAX:  # parabolic interpolation for sub-sample precision
        a, b, c = dn[tau - 1], dn[tau], dn[tau + 1]
        den = a - 2 * b + c
        shift = 0.5 * (a - c) / den if den != 0 else 0.0
    else:
        shift = 0.0
    return sr / (tau + shift)


def semitones(f0: float) -> float:
    return 12.0 * math.log2(f0 / 100.0)


@dataclass
class PhraseTracker:
    """Per-mic state. Call :meth:`feed` once per 10 ms frame."""

    buf: Array = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    pitch: deque[tuple[int, float]] = field(default_factory=deque)  # (ms, semitones)
    levels: deque[tuple[int, float]] = field(default_factory=deque)  # (ms, dB) while active
    peak_db: float = SILENCE_DB
    t_ms: int = 0
    was_active: bool = False
    pitch_falling: bool = False
    energy_fall: bool = False
    last_f0: float | None = None

    def feed(self, x16: Array, level_db: float, active: bool, pause_ms: int) -> None:
        self.t_ms += 10
        self.buf = np.concatenate([self.buf, x16])[-BUF:]
        self.last_f0 = None
        if active:
            if not self.was_active:  # a new phrase starts
                self.pitch_falling = self.energy_fall = False
                self.peak_db = level_db
            # A slowly decaying peak: the phrase's own speaking level.
            self.peak_db = max(level_db, self.peak_db - 0.05)
            self.levels.append((self.t_ms, level_db))
            if level_db >= self.peak_db - VOICED_BELOW_PEAK_DB:
                f0 = yin(self.buf)
                if f0 is not None:
                    self.last_f0 = f0
                    self.pitch.append((self.t_ms, semitones(f0)))
            while self.levels and self.t_ms - self.levels[0][0] > HISTORY_MS:
                self.levels.popleft()
            while self.pitch and self.t_ms - self.pitch[0][0] > HISTORY_MS:
                self.pitch.popleft()
        elif self.was_active:  # the phrase just ended: judge how it ended
            self.pitch_falling = self._falling()
            self.energy_fall = self._trailed_off()
            self.pitch.clear()
            self.levels.clear()
        self.was_active = active

    def phrase_end(self, pause_ms: int) -> bool:
        if pause_ms >= PHRASE_PAUSE_MS:
            return True
        return pause_ms >= SHORT_PAUSE_MS and (self.pitch_falling or self.energy_fall)

    def _end_of_speech(self) -> int:
        """When the voice really stopped: the last loud frame, not the VAD's hangover."""
        for t, db in reversed(self.levels):
            if db >= self.peak_db - VOICED_BELOW_PEAK_DB:
                return t
        return self.t_ms

    def _falling(self) -> bool:
        end = self._end_of_speech()
        tail = [st for t, st in self.pitch if end - TAIL_MS < t <= end]
        before = [st for t, st in self.pitch if end - TAIL_MS - BEFORE_MS < t <= end - TAIL_MS]
        if len(tail) < MIN_VOICED or len(before) < MIN_VOICED:
            return False
        return float(np.median(tail)) <= float(np.median(before)) - FALL_SEMITONES

    def _trailed_off(self) -> bool:
        end = self._end_of_speech()
        tail = [db for t, db in self.levels if end - ENERGY_TAIL_MS < t <= end]
        body = [db for t, db in self.levels if t <= end - ENERGY_TAIL_MS]
        if len(tail) < 5 or len(body) < 20:
            return False
        return float(np.mean(tail)) <= float(np.percentile(body, 75)) - ENERGY_FALL_DB
