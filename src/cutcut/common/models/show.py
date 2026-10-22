"""Show configuration (spec section 4). One YAML file per show in ``site/<studio>/shows/``."""

from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cutcut.common.ids import CameraId, MicId, ParticipantId

SHOW_SCHEMA_VERSION = 1


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Participant(_Strict):
    id: ParticipantId
    name: str = Field(min_length=1, max_length=40)
    mic: MicId
    camera: CameraId
    role: Literal["host", "guest"]


class CameraConfig(_Strict):
    driver: Literal["obsbot", "canon_xc", "panasonic_aw", "sony_visca", "none"]
    ip: IPv4Address | None = None
    atem_input: int = Field(ge=1, le=8)
    presets: dict[str, int] = Field(default_factory=dict)
    slow_zoom: bool = False
    role: Literal["closeup", "bird", "wide"] = "closeup"

    @model_validator(mode="after")
    def _ip_when_driven(self) -> Self:
        if self.driver != "none" and self.ip is None:
            raise ValueError(f"camera driver {self.driver!r} needs an ip")
        return self


class ContentConfig(_Strict):
    atem_input: int = Field(default=6, ge=1, le=8)
    audio_mic: MicId = MicId.M5


RETIRED_FEATURES = frozenset({"live_transcript", "turn_prediction"})  # D-063


class Features(_Strict):
    """Switches from spec 5.13. Base mode is always on; bird and content default on."""

    bird: bool = True
    content: bool = True
    video_confirm: bool = False
    reactions: bool = False
    framing_variety: bool = False
    slow_zoom: bool = False
    layouts: bool = False

    @model_validator(mode="before")
    @classmethod
    def _retired(cls, data: object) -> object:
        """Live text and turn prediction were taken out of v1 (D-063). Saved settings and old
        show files that still name them load as before."""
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if k not in RETIRED_FEATURES}
        return data


class LayoutSwitches(_Strict):
    pip_speaker_content: bool = False
    pip_two_people: bool = False
    quad_four: bool = False
    quad_three_content: bool = False


class ColorValue(_Strict):
    kelvin: int = Field(ge=2000, le=10000)
    r: int = 0
    b: int = 0


class ColorConfig(_Strict):
    reference_camera: CameraId
    saved_at: datetime | None = None
    values: dict[CameraId, ColorValue] = Field(default_factory=dict)


RulesPreset = Literal["rolig", "standard", "energisk"]


class ShowConfig(_Strict):
    schema_version: int = SHOW_SCHEMA_VERSION
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,62}$")
    name: str = Field(min_length=1, max_length=80)
    version: int = Field(default=1, ge=1)
    participants: list[Participant] = Field(min_length=1, max_length=4)
    cameras: dict[CameraId, CameraConfig]
    content: ContentConfig = ContentConfig()
    features: Features = Features()
    layouts: LayoutSwitches = LayoutSwitches()
    ai_tracking: list[CameraId] = Field(default_factory=list)
    iso_record: bool = False
    rules_preset: RulesPreset = "standard"
    rules_override: dict[str, float] = Field(default_factory=dict)
    color: ColorConfig | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [p.id for p in self.participants]
        if len(set(ids)) != len(ids):
            raise ValueError("participant ids must be unique")
        mics = [p.mic for p in self.participants]
        if len(set(mics)) != len(mics):
            raise ValueError("each participant needs their own mic")
        if MicId.M5 in mics:
            raise ValueError("M5 is laptop audio and cannot belong to a participant")
        cams = [p.camera for p in self.participants]
        if len(set(cams)) != len(cams):
            raise ValueError("each participant needs their own camera (spec 4)")
        for p in self.participants:
            if p.camera not in self.cameras:
                raise ValueError(f"{p.id} uses camera {p.camera} which is not configured")
            if self.cameras[p.camera].role != "closeup":
                raise ValueError(f"{p.id} camera {p.camera} must be a close-up camera")
        bird = self.cameras.get(CameraId.C5)
        if bird is None or bird.role != "bird":
            raise ValueError("C5 with role 'bird' is required from v1 (spec 4)")
        if CameraId.C7 in self.cameras and self.cameras[CameraId.C7].role != "wide":
            raise ValueError("C7 must have role 'wide'")
        for cam in self.ai_tracking:
            if cam not in self.cameras or self.cameras[cam].role == "bird":
                raise ValueError(f"AI tracking not allowed on {cam} (spec 5.13 AT)")
        inputs = [c.atem_input for c in self.cameras.values()] + [self.content.atem_input]
        if len(set(inputs)) != len(inputs):
            raise ValueError("ATEM inputs must be unique across cameras and content")
        if not any(p.role == "host" for p in self.participants):
            raise ValueError("at least one participant must be host")
        return self

    @property
    def has_wide(self) -> bool:
        return CameraId.C7 in self.cameras

    def participant(self, pid: ParticipantId) -> Participant:
        for p in self.participants:
            if p.id == pid:
                return p
        raise KeyError(pid)
