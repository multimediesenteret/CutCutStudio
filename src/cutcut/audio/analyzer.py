"""Per-mic measurements from multitrack blocks (AU-1 – AU-4).

Input: 10 ms blocks of the RØDECaster multitrack (480 samples × channels at 48 kHz).
Output per block: one ``audio.frame`` payload with, for each mic, the fields core reads
(``cutcut.core.messages.MicFramePayload``):

* ``level_db`` – RMS of the last 10 ms;
* ``vad`` – voice probability from the VAD, updated every 32 ms and held in between;
* ``dominance_db`` – own level minus the loudest other mic (who is talking, not leaking);
* ``pause_ms`` – how long the mic has been quiet (hysteresis 0.5 / 0.35 on ``vad``);
* ``phrase_end``, ``pitch_falling`` – phrase boundaries (:mod:`cutcut.audio.phrase`);
* ``leak`` – active only because it hears another mic (:mod:`cutcut.audio.leak`);
* ``in_main_mix`` – heard in the RØDECaster main mix, ``S6`` (:mod:`cutcut.audio.mainmix`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import numpy as np

from cutcut.audio.channels import DEFAULT_MAP, MAIN_MIX
from cutcut.audio.dsp import SILENCE_DB, Array, Decimator, rms_db
from cutcut.audio.leak import LeakDetector
from cutcut.audio.mainmix import MainMixWatch
from cutcut.audio.phrase import PhraseTracker
from cutcut.audio.vad import BLOCK, Vad, make_vad
from cutcut.common.ids import MicId

FRAME: Final = 480  # 10 ms at 48 kHz
ON: Final = 0.5
OFF: Final = 0.35
MAX_PAUSE_MS: Final = 600_000


@dataclass
class _Mic:
    channel: int
    vad: Vad
    decimator: Decimator = field(default_factory=Decimator)
    buf16: Array = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    prob: float = 0.0
    active: bool = False
    pause_ms: int = MAX_PAUSE_MS
    level_db: float = SILENCE_DB
    phrase: PhraseTracker = field(default_factory=PhraseTracker)


class Analyzer:
    def __init__(
        self,
        mics: dict[MicId, int] | None = None,
        *,
        vad_model: Path | None = None,
        leak_db: Mapping[MicId, Mapping[MicId, float]] | None = None,
        main_mix: tuple[int, int] | None = MAIN_MIX,
    ) -> None:
        self.mics = {
            mic: _Mic(channel, make_vad(vad_model))
            for mic, channel in (mics or DEFAULT_MAP).items()
        }
        self.leak = LeakDetector(leak_db)
        self.main_mix = main_mix
        self.mainmix = MainMixWatch()

    @property
    def vad_name(self) -> str:
        return next(iter(self.mics.values())).vad.name if self.mics else "none"

    def feed(self, block: Array) -> dict[str, Any]:
        """One 10 ms block (frames × channels) → one ``audio.frame`` payload."""
        for m in self.mics.values():
            x = (
                block[:, m.channel]
                if m.channel < block.shape[1]
                else np.zeros(len(block), np.float32)
            )
            m.level_db = rms_db(x)
            x16 = m.decimator(x)
            m.buf16 = np.concatenate([m.buf16, x16])
            while len(m.buf16) >= BLOCK:
                m.prob = m.vad(m.buf16[:BLOCK])
                m.buf16 = m.buf16[BLOCK:]
            if m.active and m.prob < OFF:
                m.active = False
            elif not m.active and m.prob >= ON:
                m.active = True
            m.pause_ms = 0 if m.active else min(MAX_PAUSE_MS, m.pause_ms + 10)
            m.phrase.feed(x16, m.level_db, m.active, m.pause_ms)
        levels = {mic: m.level_db for mic, m in self.mics.items()}
        active = {mic: m.active for mic, m in self.mics.items()}
        leak = self.leak.feed(levels, active)
        if self.main_mix is not None and max(self.main_mix) < block.shape[1]:
            main_db = max(rms_db(block[:, ch]) for ch in self.main_mix)
            in_mix = self.mainmix.feed(
                main_db,
                {k.value: v for k, v in levels.items()},
                {k.value: v for k, v in active.items()},
            )
        else:
            in_mix = {}
        out: dict[str, Any] = {}
        for mic, m in self.mics.items():
            others = [o.level_db for k, o in self.mics.items() if k is not mic]
            dominance = m.level_db - max(others) if others else 0.0
            out[mic.value] = {
                "vad": round(m.prob, 3),
                "level_db": round(m.level_db, 1),
                "dominance_db": round(dominance, 1),
                "pause_ms": m.pause_ms,
                "phrase_end": not m.active and m.phrase.phrase_end(m.pause_ms),
                "pitch_falling": not m.active and m.phrase.pitch_falling,
                "in_main_mix": in_mix.get(mic.value, True),
                "leak": leak.get(mic, False),
                "laughter": False,
            }
        return {"mics": out}
