"""Setup step 5: the microphones (spec 8.4, AU-7).

The technician has one person at a time say a few words in their mic, and one silent moment:

* **Right channel:** the talker's own mic must be the loudest. If another mic is louder, the
  channel map does not match the RØDECaster (wrong fader, new firmware): fix before going on.
* **Leakage:** how much quieter the voice is on every other mic (:class:`LeakMeasurer`),
  which ``audio-capture`` uses to tell talking from leaking (AU-4).
* **Noise floor:** each mic in silence, the fasit for ``H-AUD-2`` (noise + 6 dB).

Approved, the result is written to ``site/<studio>/baseline.yaml`` (``audio``) and sent to a
running ``audio-capture`` at once (``audio.config``). Measuring never changes anything on the
mixer: it only listens.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal

import numpy as np
from ruamel.yaml import YAML

from cutcut.audio.leak import TALKING_DB, LeakMeasurer
from cutcut.common.ids import MicId
from cutcut.common.models.baseline import AudioBaseline, Baseline

TALK_MS: Final = 6_000
NOISE_MS: Final = 3_000
MIN_TALK_FRAMES: Final = 100  # 1 s of speech


@dataclass
class _Run:
    kind: Literal["talk", "noise"]
    mic: MicId | None
    until: int
    levels: dict[MicId, list[float]] = field(default_factory=dict)
    talk_frames: int = 0


@dataclass
class MicResult:
    mic: MicId
    level_db: float  # median level while talking
    right_channel: bool
    loudest_other: MicId | None
    leak_db: dict[MicId, float]
    frames: int


@dataclass
class MicCheck:
    """One measuring session in the setup screen. Fed with every ``audio.frame``."""

    mics: list[MicId]
    measurer: LeakMeasurer = field(default_factory=LeakMeasurer)
    results: dict[MicId, MicResult] = field(default_factory=dict)
    noise_floor: dict[MicId, float] = field(default_factory=dict)
    running: _Run | None = None
    message: str | None = None

    def start_talk(self, mic: MicId, now: int) -> None:
        if mic not in self.mics:
            raise ValueError(f"{mic.value} er ikke i bruk i dette studioet")
        self.measurer.reset(mic)  # a new take replaces the old one
        self.running = _Run("talk", mic, now + TALK_MS)
        self.message = f"Be personen ved {mic.value} si noen setninger …"

    def start_noise(self, now: int) -> None:
        self.running = _Run("noise", None, now + NOISE_MS)
        self.message = "Stille i rommet i tre sekunder …"

    def feed(self, levels: dict[MicId, float], now: int) -> None:
        run = self.running
        if run is None:
            return
        for mic in self.mics:
            if mic in levels:
                run.levels.setdefault(mic, []).append(levels[mic])
        talker = run.mic if run.kind == "talk" else None
        if talker is not None and levels.get(talker, -90.0) >= TALKING_DB:
            run.talk_frames += 1
            self.measurer.feed(talker, {m: levels[m] for m in self.mics if m in levels})
        if now >= run.until:
            self._finish(run)

    def _finish(self, run: _Run) -> None:
        self.running = None
        if run.kind == "noise":
            self.noise_floor = {
                m: round(float(np.percentile(v, 50)), 1) for m, v in run.levels.items() if v
            }
            self.message = "Støynivået er målt."
            return
        mic = run.mic
        if mic is None:
            return
        if run.talk_frames < MIN_TALK_FRAMES:
            self.message = f"{mic.value}: hørte ikke nok tale. Prøv igjen, litt høyere."
            return
        talking = {m: v for m, v in run.levels.items() if v}
        loud = {m: float(np.percentile(v, 90)) for m, v in talking.items()}
        loudest = max(loud, key=lambda m: loud[m])
        row = self.measurer.result().get(mic, {})
        self.results[mic] = MicResult(
            mic=mic,
            level_db=round(float(np.percentile(talking[mic], 90)), 1),
            right_channel=loudest == mic,
            loudest_other=None if loudest == mic else loudest,
            leak_db=row,
            frames=run.talk_frames,
        )
        if loudest != mic:
            self.message = (
                f"{mic.value}: stemmen var sterkest på {loudest.value}. Sjekk at personen "
                f"snakker i riktig mikrofon, og at fader {mic.value[1:]} er mic {mic.value}."
            )
        else:
            self.message = f"{mic.value} er målt."

    # -- result ---------------------------------------------------------------------------------

    def done(self) -> bool:
        return all(m in self.results and self.results[m].right_channel for m in self.mics)

    def baseline(self, old: Baseline, who: str, at: datetime) -> Baseline:
        audio = AudioBaseline(
            leak_db={m: r.leak_db for m, r in self.results.items() if r.leak_db},
            noise_floor_db=self.noise_floor or old.audio.noise_floor_db,
            rodecaster_firmware=old.audio.rodecaster_firmware,
        )
        return old.model_copy(update={"audio": audio, "approved_by": who, "approved_at": at})

    def status(self, now: int) -> dict[str, Any]:
        return {
            "mics": [m.value for m in self.mics],
            "running": None
            if self.running is None
            else {
                "kind": self.running.kind,
                "mic": self.running.mic.value if self.running.mic else None,
                "left_ms": max(0, self.running.until - now),
            },
            "results": {
                m.value: {
                    "level_db": r.level_db,
                    "right_channel": r.right_channel,
                    "loudest_other": r.loudest_other.value if r.loudest_other else None,
                    "leak_db": {k.value: v for k, v in r.leak_db.items()},
                    "worst_leak_db": max(r.leak_db.values(), default=None),
                }
                for m, r in self.results.items()
            },
            "noise_floor_db": {m.value: v for m, v in self.noise_floor.items()},
            "message": self.message,
            "done": self.done(),
        }


def write_baseline(path: Path, baseline: Baseline) -> None:
    yaml = YAML()
    yaml.default_flow_style = None
    buf = io.StringIO()
    buf.write(
        "# Fasit fra setup-hjelperen (spesifikasjonen 8.4). Skrevet av CutCut Studio;\n"
        "# helsesjekkene sammenligner studioet med denne filen.\n"
    )
    yaml.dump(baseline.model_dump(mode="json", exclude_none=True), buf)
    path.write_text(buf.getvalue(), encoding="utf-8")
