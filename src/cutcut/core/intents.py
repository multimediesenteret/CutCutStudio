"""What the engine wants done (docs/plans/core.md). The runtime turns these into device
commands via Companion and atem-bridge – or only logs them in shadow mode (PL-05)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from cutcut.common.ids import CameraId, SourceId


@dataclass(frozen=True)
class SetPreview:
    """Companion page 10 row 0: put a source on preview."""

    source: SourceId


@dataclass(frozen=True)
class PrepareLayout:
    """Companion page 10 rows 1–2: run the layout macro, which puts SuperSource on preview."""

    shot: str


@dataclass(frozen=True)
class Take:
    """Companion page 10 row 3: preview to program with CUT (speaker) or MIX (layouts)."""

    transition: Literal["cut", "mix"]


@dataclass(frozen=True)
class DirectCut:
    """Straight to program, for overrides and safety (PV4). Via Companion operator page or,
    if Companion is down, directly via atem-bridge (S5)."""

    source: SourceId


@dataclass(frozen=True)
class ShowAudioOnly:
    """Mode A: the "Kun lyd" graphic from media player 1 on program (spec 2.2, 5.1)."""


@dataclass(frozen=True)
class SetCompanionVariable:
    name: str
    value: str


@dataclass(frozen=True)
class FrameCamera:
    """F1: recall the camera's ``tight`` or ``wide`` preset while it is off air (never on
    program or preview: the camera guard refuses that, I2)."""

    camera: CameraId
    framing: Literal["tight", "wide"]


@dataclass(frozen=True)
class SlowZoom:
    """Z1: zoom in by ``amount`` (share of the zoom range) over ``duration_ms``, in small
    steps, on the camera that is on air. The only movement allowed on air (I2)."""

    camera: CameraId
    amount: float
    duration_ms: int


@dataclass(frozen=True)
class StopZoom:
    """Z2: stop a slow zoom now."""

    camera: CameraId


CameraIntent = FrameCamera | SlowZoom | StopZoom

Intent = (
    SetPreview
    | PrepareLayout
    | Take
    | DirectCut
    | ShowAudioOnly
    | SetCompanionVariable
    | FrameCamera
    | SlowZoom
    | StopZoom
)
