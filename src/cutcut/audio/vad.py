"""Voice activity per mic, 0–1, on 32 ms blocks at 16 kHz (512 samples).

* :class:`SileroVad` – the studio VAD (Silero, MIT), via onnxruntime, when the model file and
  the ``silero`` extra are installed (docs/plans/audio.md).
* :class:`EnergyVad` – level above an adaptive noise floor. Good enough for synthetic test
  signals and as a reserve if the model cannot load; the studio keeps running either way.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Final, Protocol

import numpy as np

from cutcut.audio.dsp import Array, rms_db

log = logging.getLogger(__name__)

BLOCK: Final = 512  # 32 ms at 16 kHz


class Vad(Protocol):
    name: str

    def __call__(self, block: Array) -> float: ...


class EnergyVad:
    name = "energy"

    def __init__(self, margin_db: float = 15.0, floor_db: float = -70.0) -> None:
        self.margin_db = margin_db
        self.floor_db = floor_db

    def __call__(self, block: Array) -> float:
        level = rms_db(block)
        # The floor follows quiet passages quickly and loud ones very slowly.
        rate = 0.2 if level < self.floor_db else 0.002
        self.floor_db += rate * (level - self.floor_db)
        self.floor_db = min(self.floor_db, -40.0)
        x = (level - self.floor_db - self.margin_db) / 3.0
        return 1.0 / (1.0 + math.exp(-x))


class SileroVad:
    """Silero VAD v5 ONNX model (input 512 samples at 16 kHz, state 2×1×128)."""

    name = "silero"

    def __init__(self, model: Path) -> None:
        import onnxruntime as ort  # type: ignore[import-not-found,unused-ignore]  # extra «silero»

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self._session: Any = ort.InferenceSession(
            str(model), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros(64, dtype=np.float32)
        self._sr = np.array(16_000, dtype=np.int64)

    def __call__(self, block: Array) -> float:
        x = np.concatenate([self._context, block.astype(np.float32)])[None, :]
        out, self._state = self._session.run(
            None, {"input": x, "state": self._state, "sr": self._sr}
        )
        self._context = block[-64:].astype(np.float32)
        return float(out[0][0])


def make_vad(model: Path | None) -> Vad:
    """Silero when it can be loaded, otherwise the energy VAD (logged once)."""
    if model is not None and model.exists():
        try:
            return SileroVad(model)
        except Exception as exc:  # missing onnxruntime, corrupt model …
            log.warning("Silero VAD kunne ikke lastes (%s); bruker energi-VAD", exc)
    return EnergyVad()
