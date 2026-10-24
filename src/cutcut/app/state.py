"""Typed state for the screens. These models are in the OpenAPI description, and the UI's
TypeScript types are generated from it (spec 12.5: screen and engine cannot disagree)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from cutcut.common.models.decision import Decision
from cutcut.common.models.session import Session, ShowChoice
from cutcut.health.model import CheckResult


class _S(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StudioInfo(_S):
    name: str
    simulator: bool
    version: str
    show_types: dict[str, str]
    show_type: str = "podcast"  # the studio's type (Innstillinger → Show-type, SE-6)
    show_id: str
    # ATEM input per multiview tile key (P1–P4, BIRD, WIDE, CONTENT), so the screens can
    # use the same «Camera n» names as the ATEM multiview (D-054).
    inputs: dict[str, int]
    support_email: str | None = None  # shown on touch at «Hjelp» (D-065)
    debug_until: str | None = None  # feilsøkingsmodus on until (Helse); None: off


class SeatAudio(_S):
    """The audio check during the 3-2-1 countdown, per participant (AU-7)."""

    id: str
    heard: bool = False  # spoke for at least 0.3 s on their own mic
    muted: bool = False  # spoke, but is not in the RØDECaster main mix (fader down, S6)
    loud: bool = False  # close to clipping


class TouchInfo(_S):
    step: Literal["idle", "ready", "countdown", "rec", "done"]
    countdown_ms: int
    notice: str | None
    help: bool
    default_show: ShowChoice
    done_logout_ms: int
    # How users sign in (D-057): «open» = a Start button, no card; «card» = access card + API.
    login: Literal["open", "card"] = "open"
    audio_check: list[SeatAudio] = []


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
    # P10: AUTO waits because a graphic is on air, or the ATEM cannot be read
    hold: Literal["graphic", "atem"] | None = None
    hold_input: int | None = None


class ParticipantInfo(_S):
    id: str
    name: str
    role: Literal["host", "guest"]
    mic: str
    camera: str
    color: Literal["magenta", "cyan", "lilla", "oransje"]


class IsoInfo(_S):
    """ISO recording on the ATEM's disk (spec 7.7, DA-8)."""

    available: bool  # the ATEM can be read
    state: Literal["idle", "recording", "stopping", "unknown"]
    disk: str | None = None
    time_available_s: int | None = None
    error: str | None = None
    filename: str | None = None
    duration_s: int = 0
    started_by: str | None = None
    wanted: bool = False  # the show type or show records ISO with Pearl


class RecordingInfo(_S):
    pearl: Literal["idle", "starting", "started", "stopped", "error", "disabled"]
    duration_s: int
    started_by: Literal["touch", "tech", "streamdeck"] | None
    # From the real Pearl client (SE-2); the in-process fake leaves the defaults.
    online: bool = True
    error: str | None = None
    firmware: str | None = None
    storage_free_pct: int | None = None
    iso: IsoInfo | None = None


class SwitchInfo(_S):
    """One switch beyond base mode (F-1): its mode, and whether it can be used now."""

    key: str
    mode: Literal["off", "shadow", "on"]
    can_shadow: bool
    can_on: bool
    why: str | None = None  # why it cannot be switched on (or into shadow)


class RulesInfo(_S):
    preset: Literal["rolig", "standard", "energisk"]
    features: dict[str, bool]
    overrides: dict[str, float]
    switches: list[SwitchInfo] = []


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
    pid: int | None = None  # for the 72-hour test (hwtest soak), which measures it with psutil
    uptime_s: int = 0
    restarts_10min: int = 0
    last_reason: str | None = None


class RuntimeInfo(_S):
    ticks: int
    max_step_ms: float
    skipped_ticks: int
    processes: list[ProcessInfo] = []  # empty when core runs without the supervisor
    vision: bool = False  # the video layer delivers pictures: cut-outs instead of drawings


class MorningCheck(_S):
    """The whole catalogue, run at start-up and every morning at 07:00 (spec 8.5, HS-4)."""

    ts: str
    reason: Literal["oppstart", "morgen", "manuell"]
    status: Literal["green", "yellow", "red"]
    failed: list[str] = []  # check IDs that were not green, worst first


class HealthInfo(_S):
    """The health checks (spec 8.5): worst open issue and the latest result of each check."""

    status: Literal["green", "yellow", "red"] = "green"
    checks: list[CheckResult] = []
    morning: MorningCheck | None = None


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
    health: HealthInfo = HealthInfo()


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
