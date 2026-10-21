"""Scenario files (``sim/scenarios/*.yaml``) and the runner that checks their expectations.

Scenarios drive the same engine and runtime as the studio, on a fake clock, much faster than
real time. They are used by the tests, by ``cutcut sim`` and to make the traces that the web
simulator on Vercel plays back (docs/simulator.md, ADR-0013).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cutcut.common.config.loader import ConfigError, read_yaml
from cutcut.common.ids import CameraId, ParticipantId, RuleId
from cutcut.common.models.show import RulesPreset
from cutcut.core.inputs import ContentState


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Step(_M):
    at: float = Field(ge=0, description="seconds from start")
    talk: ParticipantId | None = None
    stop: ParticipantId | None = None
    for_: float | None = Field(default=None, alias="for", ge=0)
    dominance: float = 12.0
    pitch_falling: bool = True
    content: ContentState | None = None
    laptop_audio: bool | None = None
    laugh: list[ParticipantId] | None = None
    mute: ParticipantId | None = None
    unmute: ParticipantId | None = None
    command: (
        Literal["auto_off", "auto_on", "lock", "unlock", "content_off", "content_on"] | None
    ) = None
    manual_cut: str | None = None
    operator_cut: str | None = None  # a person cuts on the ATEM itself (I5)


FaultKind = Literal[
    "audio_lost", "atem_down", "companion_down", "camera_moving", "video_down", "pearl_fail"
]


class Fault(_M):
    at: float = Field(ge=0)
    kind: FaultKind
    for_: float | None = Field(default=None, alias="for", ge=0)
    camera: CameraId | None = None


Never = Literal[
    "cut_to_moving_camera",
    "cuts_faster_than_1s",
    "content_on_air_without_signal",
    "auto_cut_while_paused",
]


class Expect(_M):
    rule: RuleId | None = None
    action: Literal["cut", "wait", "hold", "preview", "any"] = "cut"
    between_s: tuple[float, float] | None = None
    never: Never | None = None
    min_cuts: int | None = None
    max_cuts_per_10min: float | None = None
    shot_seen: str | None = None
    shot_not_seen: str | None = None
    program_at_end: str | None = None
    after_s: float = 0.0  # shot_seen / shot_not_seen only look at cuts after this time


class Scenario(_M):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    description: str
    seed: int = 1
    show: str
    preset: RulesPreset = "standard"
    features: dict[str, bool] = Field(default_factory=dict)
    wide: bool = False
    duration_s: float = Field(gt=0, le=4 * 3600)
    conversation: bool = False
    start_show: bool = True
    script: list[Step] = Field(default_factory=list)
    faults: list[Fault] = Field(default_factory=list)
    expect: list[Expect] = Field(default_factory=list)


def scenarios_dir() -> Path:
    from cutcut.common.config import default_config_dir

    return default_config_dir().parent / "sim" / "scenarios"


def load_scenario(path: Path) -> Scenario:
    try:
        return Scenario.model_validate(read_yaml(path))
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def all_scenarios() -> list[Path]:
    return sorted(scenarios_dir().glob("*.yaml"))
