"""Fixed IDs from the specification glossary (spec "Ordliste og faste ID-er", D-041).

IDs are used unchanged in code, logs, tests and the UI. Display names for the UI
("CAM 1", "IN 6") live in the UI language file, not here.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Final

from pydantic import AfterValidator


class ParticipantId(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class MicId(StrEnum):
    """RØDECaster faders 1–5. M1–M4 belong to P1–P4; M5 is laptop audio (CT3, CT5)."""

    M1 = "M1"
    M2 = "M2"
    M3 = "M3"
    M4 = "M4"
    M5 = "M5"


class CameraId(StrEnum):
    """Camera IDs. C1–C4 close-ups (ATEM inputs 1–4), C5 bird's-eye, C7 optional wide."""

    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"
    C5 = "C5"
    C7 = "C7"


class SourceId(StrEnum):
    """Everything that can be routed in the ATEM: cameras, the laptop and SuperSource."""

    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"
    C5 = "C5"
    LAPTOP = "LAPTOP"
    C7 = "C7"
    SUPERSOURCE = "SUPERSOURCE"


class Mode(StrEnum):
    """Engine mode (spec 5.1): N1–N4 by participants, NxC with content, A audio only."""

    N1 = "N1"
    N2 = "N2"
    N3 = "N3"
    N4 = "N4"
    N1C = "N1C"
    N2C = "N2C"
    N3C = "N3C"
    N4C = "N4C"
    A = "A"

    @classmethod
    def for_show(cls, participants: int, content_active: bool, audio_only: bool = False) -> Mode:
        if audio_only:
            return cls.A
        if not 1 <= participants <= 4:
            raise ValueError(f"participants must be 1–4, got {participants}")
        return cls(f"N{participants}{'C' if content_active else ''}")

    @property
    def participants(self) -> int | None:
        return None if self is Mode.A else int(self.value[1])

    @property
    def content(self) -> bool:
        return self.value.endswith("C")


class RuleId(StrEnum):
    """Every rule ID in the specification (section 5–6). Each must have tests (spec 12.1).

    ``MANUAL`` marks operator overrides (spec 5.2 step 1), which have no rule ID in the spec.
    """

    # Talk (5.3). T10 and T11 do not exist in the spec.
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"
    T5 = "T5"
    T6 = "T6"
    T7 = "T7"
    T8 = "T8"
    T9 = "T9"
    T12 = "T12"
    # Bird's-eye (5.4)
    B1 = "B1"
    B2 = "B2"
    B3 = "B3"
    B4 = "B4"
    B5 = "B5"
    # Content (5.5)
    CT1 = "CT1"
    CT2 = "CT2"
    CT3 = "CT3"
    CT4 = "CT4"
    CT5 = "CT5"
    CT6 = "CT6"
    # Layouts (5.6)
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"
    # Safety (5.7)
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"
    S5 = "S5"
    S6 = "S6"
    # Preview (5.9)
    PV1 = "PV1"
    PV2 = "PV2"
    PV3 = "PV3"
    PV4 = "PV4"
    # Cut points (5.10)
    K1 = "K1"
    K2 = "K2"
    K3 = "K3"
    K4 = "K4"
    # Hold and release (5.11)
    H1 = "H1"
    H2 = "H2"
    H3 = "H3"
    H4 = "H4"
    # Reactions, framing, zoom, AI tracking (5.13)
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    F1 = "F1"
    F2 = "F2"
    F3 = "F3"
    Z1 = "Z1"
    Z2 = "Z2"
    Z3 = "Z3"
    AT1 = "AT1"
    AT2 = "AT2"
    AT3 = "AT3"
    AT4 = "AT4"
    AT5 = "AT5"
    AT6 = "AT6"
    # Video (6.5)
    V1 = "V1"
    V2 = "V2"
    V3 = "V3"
    V4 = "V4"
    V5 = "V5"
    V6 = "V6"
    # Operator override (5.2 step 1)
    MANUAL = "MANUAL"


# --- Shots -------------------------------------------------------------------------------
# A shot is what goes to program (spec glossary). Kept as validated strings so they are
# cheap, hashable, JSON-friendly and identical in logs, API and UI.

BIRD: Final = "BIRD"
WIDE: Final = "WIDE"
CONTENT: Final = "CONTENT"
QUAD4: Final = "QUAD4"
QUAD3C: Final = "QUAD3C"
AUDIO_ONLY: Final = "AUDIO_ONLY"  # media player 1 "Kun lyd" graphic, mode A (spec 2.2)

_SHOT_RE = re.compile(
    r"^(?:BIRD|WIDE|CONTENT|QUAD4|QUAD3C|AUDIO_ONLY"
    r"|CU:P[1-4]"
    r"|PIP:P[1-4]\+CONTENT"
    r"|PIP:P([1-4])\+P([1-4]))$"
)


def _validate_shot(value: str) -> str:
    match = _SHOT_RE.match(value)
    if match is None:
        raise ValueError(f"unknown shot {value!r}")
    first, second = match.group(1), match.group(2)
    if first is not None and second is not None and first >= second:
        raise ValueError(f"two-person PiP must list participants in order, got {value!r}")
    return value


Shot = Annotated[str, AfterValidator(_validate_shot)]
"""Validated shot string: ``CU:P2``, ``BIRD``, ``WIDE``, ``CONTENT``, ``PIP:P2+CONTENT``,
``PIP:P1+P2``, ``QUAD4``, ``QUAD3C`` or ``AUDIO_ONLY``."""


def is_shot(value: str) -> bool:
    try:
        _validate_shot(value)
    except ValueError:
        return False
    return True


def close_up(participant: ParticipantId) -> str:
    return f"CU:{participant.value}"


def pip_content(participant: ParticipantId) -> str:
    return f"PIP:{participant.value}+CONTENT"


def pip_two(a: ParticipantId, b: ParticipantId) -> str:
    if a == b:
        raise ValueError("two-person PiP needs two different participants")
    first, second = sorted((a.value, b.value))
    return f"PIP:{first}+{second}"


def shot_participants(shot: str) -> tuple[ParticipantId, ...]:
    """Participants visible in a shot (empty for BIRD, WIDE, CONTENT …)."""
    _validate_shot(shot)
    if shot == QUAD4:
        return (ParticipantId.P1, ParticipantId.P2, ParticipantId.P3, ParticipantId.P4)
    if shot == QUAD3C:
        return (ParticipantId.P1, ParticipantId.P2, ParticipantId.P3)
    return tuple(ParticipantId(p) for p in re.findall(r"P[1-4]", shot))


def is_layout(shot: str) -> bool:
    """Layouts are built with ATEM macros and taken with MIX (spec 5.6, 7.1)."""
    return shot.startswith("PIP:") or shot in (QUAD4, QUAD3C)
