"""Bus payloads the core reads, and how they become engine inputs.

Topics (docs/plans/audio.md, devices-companion-atem.md, vision.md):

* ``audio.frame``  – ``{"mics": {"M1": {MicFrame fields}, ...}}`` from audio-capture (100 Hz)
* ``vision.content`` – ``{"state": "NEW_SLIDE", "changed_ratio": 0.42}`` (spec 6.6)
* ``vision.tile`` – ``{"source": "C2", "face": {"found": true, ...}, "mouth": .., "moving": ..}``
* ``atem.state`` – ``{"program": "C2", "preview": "C5", "program_layout": null}``
* ``cameras.moving`` – ``{"moving": ["C3"]}`` from the camera drivers (S1)
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from cutcut.common.ids import CameraId, MicId, SourceId
from cutcut.core.inputs import AtemReadback, ContentState, MicFrame, TileFrame


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class MicFramePayload(_Payload):
    vad: float = Field(ge=0, le=1)
    level_db: float = -90.0
    dominance_db: float = 0.0
    pause_ms: int = Field(default=10_000, ge=0)
    phrase_end: bool = False
    pitch_falling: bool = False
    in_main_mix: bool = True
    leak: bool = False
    laughter: bool = False


class AudioFramePayload(_Payload):
    mics: dict[MicId, MicFramePayload]


class ContentPayload(_Payload):
    state: ContentState
    changed_ratio: float = 0.0


class FacePayload(_Payload):
    found: bool = False
    size_ok: bool = False


class TilePayload(_Payload):
    source: SourceId
    face: FacePayload = FacePayload()
    mouth: float = 0.0
    smile: float = 0.0
    moving: bool = False


class AtemStatePayload(_Payload):
    program: SourceId
    preview: SourceId
    program_layout: str | None = None


class CamerasMovingPayload(_Payload):
    moving: list[CameraId] = Field(default_factory=list)


def mic_frames(payload: dict[str, Any]) -> dict[MicId, MicFrame]:
    parsed = AudioFramePayload.model_validate(payload)
    return {mic: MicFrame(**frame.model_dump()) for mic, frame in parsed.mics.items()}


def content_state(payload: dict[str, Any]) -> ContentState:
    return ContentPayload.model_validate(payload).state


def tile(payload: dict[str, Any]) -> tuple[SourceId, TileFrame]:
    p = TilePayload.model_validate(payload)
    return p.source, TileFrame(
        face_ok=p.face.found and p.face.size_ok, mouth=p.mouth, smile=p.smile, moving=p.moving
    )


def atem_readback(payload: dict[str, Any]) -> AtemReadback:
    p = AtemStatePayload.model_validate(payload)
    return AtemReadback(program=p.program, preview=p.preview, program_layout=p.program_layout)


def cameras_moving(payload: dict[str, Any]) -> frozenset[CameraId]:
    return frozenset(CamerasMovingPayload.model_validate(payload).moving)
