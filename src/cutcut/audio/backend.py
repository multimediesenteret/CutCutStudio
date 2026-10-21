"""Where the multitrack comes from (``audio.backend``). AU-1: ``fake`` plays a WAV file;
AU-5 adds ASIO and WASAPI through sounddevice."""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Protocol

import numpy as np

from cutcut.audio.analyzer import FRAME
from cutcut.audio.channels import SAMPLE_RATE
from cutcut.audio.dsp import Array


class Backend(Protocol):
    name: str

    def read(self) -> Array | None:
        """The next 10 ms block (frames × channels), or None if nothing is available."""
        ...

    def close(self) -> None: ...


class WavBackend:
    """Plays a multichannel 48 kHz PCM WAV in 10 ms blocks, looping (tests, simulator)."""

    name = "fake"

    def __init__(self, path: Path, *, loop: bool = True) -> None:
        with wave.open(str(path), "rb") as w:
            if w.getframerate() != SAMPLE_RATE:
                raise ValueError(f"{path}: {w.getframerate()} Hz, forventer {SAMPLE_RATE}")
            if w.getsampwidth() != 2:
                raise ValueError(f"{path}: bare 16-bit PCM støttes")
            channels = w.getnchannels()
            raw = w.readframes(w.getnframes())
        data = np.frombuffer(raw, dtype="<i2").reshape(-1, channels)
        self.data = (data.astype(np.float32) / 32768.0).copy()
        self.loop = loop
        self.pos = 0

    def read(self) -> Array | None:
        if self.pos + FRAME > len(self.data):
            if not self.loop:
                return None
            self.pos = 0
        block = self.data[self.pos : self.pos + FRAME]
        self.pos += FRAME
        return block

    def close(self) -> None:
        return None


def write_wav(path: Path, data: Array) -> None:
    """Write frames × channels float32 as 16-bit PCM 48 kHz (test signals, maskintest)."""
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())
