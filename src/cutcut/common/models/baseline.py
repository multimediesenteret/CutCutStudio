"""``site/<studio>/baseline.yaml``: what the setup wizard measured and the technician approved
(spec 8.4, 9.3). Health compares the studio against it; audio-capture reads the leakage.

Only the audio part exists so far (AU-4). Cameras, ATEM and Pearl are added with their
setup steps.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cutcut.common.ids import MicId


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AudioBaseline(_Strict):
    """Leakage between mics, measured in setup step 5 (one person talks at a time).

    ``leak_db[A][B]`` is how much quieter A's voice is on B's mic than on A's own, in dB
    (negative; typically −15 to −30 in a small studio). Missing pairs use the default.
    """

    leak_db: dict[MicId, dict[MicId, float]] = Field(default_factory=dict)
    noise_floor_db: dict[MicId, float] = Field(default_factory=dict)  # for H-AUD-2
    rodecaster_firmware: str | None = None

    @model_validator(mode="after")
    def _pairs(self) -> Self:
        for src, row in self.leak_db.items():
            for dst, db in row.items():
                if src == dst:
                    raise ValueError(f"leak_db.{src}.{dst}: en mic lekker ikke til seg selv")
                if not -90.0 <= db <= 0.0:
                    raise ValueError(f"leak_db.{src}.{dst}: {db} dB må være mellom −90 og 0")
        return self


class Baseline(_Strict):
    schema_version: Literal[1] = 1
    approved_by: str | None = None
    approved_at: datetime | None = None
    audio: AudioBaseline = Field(default_factory=AudioBaseline)
