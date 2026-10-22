"""Everything the engine gets from outside, once per tick (docs/plans/core.md, PL-04).

The engine never reads a clock, a socket or a file. The runtime shell fills ``Inputs``
from the bus and the simulator fills it from scenarios – with exactly the same types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from cutcut.common.config.rules import RuleParams
from cutcut.common.ids import CameraId, MicId, SourceId
from cutcut.common.models.show import Features, ShowConfig


@dataclass(frozen=True)
class MicFrame:
    """Latest measurements for one mic, made by ``audio-capture`` (PL-02, docs/plans/audio.md).

    * ``vad``: speech probability 0–1 (Silero).
    * ``dominance_db``: how far this mic is above what leakage from the other mics explains.
      Two people talking at once can both be dominant; a mic that only picks up a neighbour
      is not.
    * ``pause_ms``: how long this mic has been without speech (0 while speaking).
    * ``phrase_end``: a phrase boundary was detected at the start of the current pause.
    * ``pitch_falling``: pitch fell towards the end of the last phrase (sentence end, K2).
    * ``in_main_mix``: the mic is audible in the RØDECaster main mix (False = muted, S6).
    * ``leak``: activity on this mic is explained by another mic (V1/T1 leakage).
    * ``laughter``: laughter detected on this mic (B4).
    """

    vad: float = 0.0
    level_db: float = -90.0
    dominance_db: float = 0.0
    pause_ms: int = 10_000
    phrase_end: bool = False
    pitch_falling: bool = False
    in_main_mix: bool = True
    leak: bool = False
    laughter: bool = False


SILENT = MicFrame()


@dataclass(frozen=True)
class TileFrame:
    """Video measurements for one source (spec 6.6). Only used with ``video_confirm``."""

    face_ok: bool = True
    mouth: float = 0.0
    smile: float = 0.0
    moving: bool = False


class ContentState(StrEnum):
    """Spec 6.2."""

    NO_SIGNAL = "NO_SIGNAL"
    STATIC = "STATIC"
    NEW_SLIDE = "NEW_SLIDE"
    VIDEO = "VIDEO"


@dataclass(frozen=True)
class AtemReadback:
    """What the ATEM actually shows (read by atem-bridge). Sources, not shots."""

    program: SourceId
    preview: SourceId
    program_layout: str | None = None  # layout shot when program is SuperSource


# --- operator commands (spec 5.2 step 1, 10.1) -----------------------------------------


@dataclass(frozen=True)
class SetAuto:
    on: bool


@dataclass(frozen=True)
class SetLock:
    on: bool


@dataclass(frozen=True)
class ManualCut:
    shot: str


@dataclass(frozen=True)
class ManualPreview:
    shot: str


@dataclass(frozen=True)
class SetContentEnabled:
    enabled: bool


@dataclass(frozen=True)
class SetShadow:
    on: bool


@dataclass(frozen=True)
class StartShow:
    """Session started recording: begins the opening (B1). ``audio_only`` gives mode A."""

    audio_only: bool = False


@dataclass(frozen=True)
class EndShow:
    pass


Command = (
    SetAuto
    | SetLock
    | ManualCut
    | ManualPreview
    | SetContentEnabled
    | SetShadow
    | StartShow
    | EndShow
)


@dataclass(frozen=True)
class EngineConfig:
    show: ShowConfig
    rules: RuleParams
    features: Features

    @classmethod
    def from_show(cls, show: ShowConfig, rules: RuleParams) -> EngineConfig:
        return cls(show=show, rules=rules, features=show.features)


@dataclass(frozen=True)
class Inputs:
    now_ms: int
    mics: dict[MicId, MicFrame] = field(default_factory=dict)
    audio_age_ms: int = 0  # ms since the last audio frame (S4)
    vision: dict[SourceId, TileFrame] | None = None  # None = video layer down
    content: ContentState | None = None  # None = no content measurement
    atem: AtemReadback | None = None  # None = ATEM not readable
    cameras_moving: frozenset[CameraId] = frozenset()  # from PTZ position readback (S1)
    cameras_tracking: frozenset[CameraId] = frozenset()  # AI-tracking on (AT3, AT4)
    companion_ok: bool = True
    commands: tuple[Command, ...] = ()
