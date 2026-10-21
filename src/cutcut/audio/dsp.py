"""Small signal helpers on numpy arrays (float32, -1..1). No allocations in hot paths that
can be avoided; everything here runs 100 times a second for five mics."""

from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt

Array = npt.NDArray[np.float32]

SILENCE_DB: Final = -90.0


def rms_db(x: Array) -> float:
    if x.size == 0:
        return SILENCE_DB
    rms = float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))
    return max(SILENCE_DB, 20.0 * np.log10(rms)) if rms > 0 else SILENCE_DB


def _lowpass_taps(n: int = 47, cutoff: float = 7_000 / 48_000) -> Array:
    """Windowed-sinc low-pass for 48 → 16 kHz (cut below the new Nyquist, 8 kHz)."""
    m = np.arange(n) - (n - 1) / 2
    h = np.sinc(2 * cutoff * m) * np.hamming(n)
    taps: Array = (h / h.sum()).astype(np.float32)
    return taps


_TAPS: Final = _lowpass_taps()


class Decimator:
    """48 kHz → 16 kHz, streaming: keeps the filter tail between blocks."""

    def __init__(self) -> None:
        self._tail = np.zeros(len(_TAPS) - 1, dtype=np.float32)
        self._pos = 0  # input samples seen so far

    def __call__(self, x: Array) -> Array:
        buf = np.concatenate([self._tail, x.astype(np.float32, copy=False)])
        y = np.convolve(buf, _TAPS, mode="valid")  # one output per input sample of x
        self._tail = buf[-(len(_TAPS) - 1) :]
        out = y[(-self._pos) % 3 :: 3]
        self._pos += len(x)
        return out.astype(np.float32, copy=False)
