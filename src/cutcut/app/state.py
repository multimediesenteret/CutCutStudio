"""Typed state for the screens. These models are in the OpenAPI description, and the UI's
TypeScript types are generated from it (spec 12.5: screen and engine cannot disagree)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from cutcut.common.models.decision import Decision
from cutcut.common.models.session import Session, ShowChoice


class _S(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StudioInfo(_S):
    name: str
    simulator: bool
    version: str
    show_types: dict[str, str]
    show_id: str
    # ATEM input per multiview tile key (P1–P4, BIRD, WIDE, CONTENT), so the screens can
    # use the same «Camera n» names as the ATEM multiview (D-054).
    inputs: dict[str, int]


class TouchInfo(_S):
    step: Literal["idle", "ready", "countdown", "rec", "done"]
    countdown_ms: int
    notice: str | None
    help: bool
    default_show: ShowChoice
    done_logout_ms: int


class EngineInfo(_S):
    mode: str
    program: str
    preview: str | None
    pv_state: Literal["IDLE", "ARMED", "READY"]
    auto: bool
    lock: bool
    shadow: bool
    paused: bool
    content_enabled: bool
    content_active: bool
    audio_ok: bool
    program_ms: int


class ParticipantInfo(_S):
    id: str
    name: str
    role: Literal["host", "guest"]
    mic: str
    camera: str
    color: Literal["magenta", "cyan", "lilla", "oransje"]


class RecordingInfo(_S):
    pearl: Literal["idle", "starting", "started", "stopped", "error", "disabled"]
    duration_s: int
    started_by: Literal["touch", "tech", "streamdeck"] | None
    # From the real Pearl client (SE-2); the in-process fake leaves the defaults.
    online: bool = True
    error: str | None = None
    firmware: str | None = None
    storage_free_pct: int | None = None


class RulesInfo(_S):
    preset: Literal["rolig", "standard", "energisk"]
    features: dict[str, bool]
    overrides: dict[str, float]


class AlertInfo(_S):
    id: int
    level: Literal["info", "warn", "error"]
    code: str
    message: str
    ts: str
    for_user: bool
    acknowledged: bool


class ProcessInfo(_S):
    """One process as the supervisor last reported it (``H-PROC-*``)."""

    name: str
    running: bool
    uptime_s: int = 0
    restarts_10min: int = 0
    last_reason: str | None = None


class RuntimeInfo(_S):
    ticks: int
    max_step_ms: float
    skipped_ticks: int
    processes: list[ProcessInfo] = []  # empty when core runs without the supervisor


class StudioState(_S):
    studio: StudioInfo
    session: Session | None
    touch: TouchInfo
    engine: EngineInfo
    participants: list[ParticipantInfo]
    recording: RecordingInfo
    rules: RulesInfo
    alerts: list[AlertInfo]
    runtime: RuntimeInfo


class Meter(_S):
    level_db: float
    vad: float
    speaking: bool = False
    muted: bool = False


class LiveMessage(_S):
    """Messages on ``/ws``. ``state`` carries changed top-level keys of ``StudioState``
    (all of them when ``full`` is true); ``meters`` maps mic id to ``Meter``."""

    type: Literal["state", "meters", "decision", "alert", "touch", "session", "health", "vision"]
    seq: int
    full: bool = False
    data: dict[str, object]


class LiveSchemas(_S):
    """Not sent as such: lists the payload models so they appear in the API description."""

    state: StudioState
    meter: Meter
    decision: Decision
    alert: AlertInfo
    message: LiveMessage
