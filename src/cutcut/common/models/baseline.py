"""``site/<studio>/baseline.yaml``: what the setup wizard measured and the technician approved
(spec 8.4, 9.3). Health compares the studio against it; audio-capture reads the leakage.

Audio (AU-4) and the ATEM (HS-7: format, input names, AUX outputs) so far. Cameras and Pearl
are added with their setup steps.
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


class AtemBaseline(_Strict):
    """The ATEM as the technician approved it (setup, «Lagre ATEM som fasit»). ``H-ATEM-2``
    says when someone has changed it."""

    video_mode: str = "1080p50"
    input_names: dict[int, str] = Field(default_factory=dict)  # input → long name
    aux: list[str] = Field(default_factory=list)  # what each AUX shows; AUX 2 is HDMI out 2
    approved_by: str | None = None
    approved_at: datetime | None = None


class VideoBaseline(_Strict):
    """The capture card as measured by ``cutcut hwtest vision`` (``H-VID-2``)."""

    width: int = 1920
    height: int = 1080
    delay_ms: float | None = None


class Baseline(_Strict):
    schema_version: Literal[1] = 1
    approved_by: str | None = None
    approved_at: datetime | None = None
    audio: AudioBaseline = Field(default_factory=AudioBaseline)
    atem: AtemBaseline | None = None
    video: VideoBaseline | None = None
