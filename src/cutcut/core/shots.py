"""Shot selection per mode (spec 5.1) and shot ↔ ATEM source mapping."""

from __future__ import annotations

from cutcut.common.ids import (
    AUDIO_ONLY,
    BIRD,
    CONTENT,
    WIDE,
    CameraId,
    Mode,
    ParticipantId,
    SourceId,
    close_up,
    is_layout,
    shot_participants,
)
from cutcut.common.models.show import Features, ShowConfig


def available(shot: str, show: ShowConfig, features: Features) -> bool:
    """Whether a shot can be used at all with this show and these switches."""
    if shot == BIRD:
        return features.bird and CameraId.C5 in show.cameras
    if shot == WIDE:
        return show.has_wide
    if shot == CONTENT:
        return features.content
    if is_layout(shot):
        return features.layouts
    return True


def first_available(candidates: list[str], show: ShowConfig, features: Features) -> str | None:
    for shot in candidates:
        if available(shot, show, features):
            return shot
    return None


def crosstalk_shot(mode: Mode, show: ShowConfig, features: Features) -> str | None:
    """Column "Krysstale" (5.1): N2 → WIDE else BIRD; N3/N4 → BIRD. None in N1."""
    if mode.participants in (None, 1):
        return None
    order = [WIDE, BIRD] if mode.participants == 2 else [BIRD]
    return first_available(order, show, features)


def silence_shot(mode: Mode, show: ShowConfig, features: Features) -> str | None:
    """Column "Stillhet" (5.1) with B3: content if active, else WIDE first in N1/N2, else BIRD."""
    if mode.content and features.content:
        return CONTENT
    order = [WIDE, BIRD] if mode.participants in (1, 2) else [BIRD]
    return first_available(order, show, features)


def pingpong_shot(mode: Mode, show: ShowConfig, features: Features) -> str | None:
    """Column "Ping-pong" (5.1)."""
    return crosstalk_shot(mode, show, features)


def fallback_shot(mode: Mode, show: ShowConfig, features: Features) -> str:
    """The mode's reserve shot: what preview shows when idle and where safety rules cut to."""
    shot = first_available([BIRD, WIDE], show, features)
    if shot is not None:
        return shot
    return close_up(show.participants[0].id)


def source_for(shot: str, show: ShowConfig) -> SourceId:
    """ATEM source for a shot. Layouts and the audio-only graphic are not plain sources."""
    if shot == BIRD:
        return SourceId.C5
    if shot == WIDE:
        return SourceId.C7
    if shot == CONTENT:
        return SourceId.LAPTOP
    if is_layout(shot):
        return SourceId.SUPERSOURCE
    if shot == AUDIO_ONLY:
        raise ValueError("AUDIO_ONLY is a media player, not a source")
    (pid,) = shot_participants(shot)
    return SourceId(show.participant(pid).camera.value)


def shot_for(source: SourceId, show: ShowConfig, layout: str | None = None) -> str | None:
    """Reverse of ``source_for``: which shot a source on program means (for ATEM readback)."""
    if source is SourceId.C5:
        return BIRD
    if source is SourceId.C7:
        return WIDE
    if source is SourceId.LAPTOP:
        return CONTENT
    if source is SourceId.SUPERSOURCE:
        return layout
    for p in show.participants:
        if p.camera.value == source.value:
            return close_up(p.id)
    return None


def camera_of(shot: str, show: ShowConfig) -> CameraId | None:
    """The PTZ camera that would be on air for a single-camera shot (for S1)."""
    if shot in (CONTENT, AUDIO_ONLY) or is_layout(shot):
        return None
    source = source_for(shot, show)
    return CameraId(source.value)


def speaker_of(shot: str) -> ParticipantId | None:
    """The single participant a close-up shows."""
    if shot.startswith("CU:"):
        return ParticipantId(shot[3:])
    return None
