"""What the engine wants done (docs/plans/core.md). The runtime turns these into device
commands via Companion and atem-bridge – or only logs them in shadow mode (PL-05)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from cutcut.common.ids import SourceId


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


Intent = SetPreview | PrepareLayout | Take | DirectCut | ShowAudioOnly | SetCompanionVariable
