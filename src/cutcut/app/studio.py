"""The studio as one service: engine, session, recorder, alerts and live data for the screens.

All state lives here, not in the screens (12.5): the API reads it and sends commands to it,
and the screens get a full snapshot on connect and changes afterwards. The same class runs in
the studio (real devices) and in ``cutcut sim`` (fake devices and synthetic talkers).
"""

from __future__ import annotations

import asyncio
import base64
import functools
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, tzinfo
from pathlib import Path
from typing import Any, Final, Literal, Protocol

from pydantic import ValidationError

from cutcut import __version__
from cutcut.app import devices, setup_file
from cutcut.app.hub import Hub
from cutcut.app.state import (
    AlertInfo,
    EngineInfo,
    HealthInfo,
    IsoInfo,
    Meter,
    MorningCheck,
    ParticipantInfo,
    ProcessInfo,
    RecordingInfo,
    RulesInfo,
    RuntimeInfo,
    SeatAudio,
    StudioInfo,
    StudioState,
    SwitchInfo,
    TouchInfo,
)
from cutcut.common.clock import Clock
from cutcut.common.config import (
    ConfigError,
    RuleParams,
    RulePresets,
    ShowType,
    ShowTypes,
    Site,
    default_config_dir,
    effective_rules,
)
from cutcut.common.ids import CameraId, MicId, RuleId, is_shot
from cutcut.common.models.baseline import AtemBaseline, Baseline
from cutcut.common.models.decision import Decision
from cutcut.common.models.multiview import MultiviewMap, MultiviewReadback
from cutcut.common.models.session import (
    GUEST_USER,
    RecordingStatus,
    Session,
    ShowChoice,
    StartedBy,
    TouchStep,
    User,
)
from cutcut.common.models.show import (
    SWITCHES,
    FeatureMode,
    Features,
    RulesPreset,
    ShowConfig,
)
from cutcut.common.models.site import Devices, SmtpConfig, Staff
from cutcut.common.platform.system import System
from cutcut.common.store import Store
from cutcut.core.engine import Engine, StepResult
from cutcut.core.inputs import (
    EngineConfig,
    ManualCut,
    ManualPreview,
    MicFrame,
    SetAuto,
    SetContentEnabled,
    SetLock,
    SetShadow,
)
from cutcut.core.intents import (
    FrameCamera,
    Intent,
    NudgeCamera,
    SetCompanionVariable,
    SlowZoom,
    StopZoom,
)
from cutcut.core.runtime import CoreRuntime, Executor
from cutcut.devices.atem import iso
from cutcut.devices.atem.bridge import AtemStateRaw
from cutcut.devices.atem.iso import IsoRecorder, IsoStatus
from cutcut.devices.atem.macros import check as macro_check
from cutcut.devices.cameras.base import CameraCommand, Nudge, RecallPreset, StorePreset
from cutcut.devices.cameras.service import CameraService
from cutcut.health import HealthCheck, HealthEngine, HealthEvent
from cutcut.health import checks as health_checks
from cutcut.health.notify import Notifier
from cutcut.session.manager import (
    DONE_LOGOUT_MS,
    Action,
    Alert,
    EngineCommand,
    Notice,
    PearlStart,
    PearlStop,
    SessionError,
    SessionManager,
)
from cutcut.setup import multiview as mv
from cutcut.setup.mic_check import MicCheck, write_baseline
from cutcut.setup.steps import Approval, SetupStep, StepView, load_steps, results_for, step_state

log = logging.getLogger(__name__)

STATE_EVERY_MS: Final = 100  # 10 Hz (docs/design/gui-konsept.md)
METERS_EVERY_MS: Final = 50  # 20 Hz (spec 10.2)
LOG_KEEP: Final = 200
TUNING_KEY: Final = "studio.tuning"
LOGIN_KEY: Final = "studio.login"
# Switches whose rules exist (docs/plans/for-studio.md); the others say they are being built.
IMPLEMENTED_SWITCHES: Final = frozenset(
    {"video_confirm", "reactions", "layouts", "framing_variety", "slow_zoom", "ai_tracking"}
)
VERDICT_TEXT: Final[dict[str, str]] = {
    "on_program": "Kameraet er på program (I2). Prøv når det er av lufta.",
    "on_preview": "Kameraet er på preview (PV2). Prøv når det er av lufta.",
    "no_atem": "ATEM kan ikke leses, så CutCut vet ikke hva som er på lufta.",
    "breaker_open": "Kameraet svarer ikke. CutCut prøver igjen om litt.",
    "invalid": "Ugyldig preset.",
    "tracking": "Kameraet følger personen selv (AT3). Slå av AI-tracking først.",
}
MV_KEY: Final = "setup.multiview_map"  # rutekart saved in the app (VI-5), over the file
SETUP_KEY: Final = "setup.approvals"  # step id → who approved it and when (HS-5)
SHOW_TYPE_KEY: Final = "studio.show_type"  # podcast, intervju, panel, kun-lyd (SE-6, D-036)
STAFF_KEY: Final = "site.staff"  # technicians, entered in the app (not in the repository)
LoginMode = Literal["open", "card"]
HISTORY_KEEP: Final = 200
# The multiview is set up once and not changed during use, so it is checked at start-up
# (as soon as the ATEM can be read, or after this long without it) and on request (D-056).
MULTIVIEW_STARTUP_WAIT_MS: Final = 30_000
MORNING_HOUR: Final = 7  # spec 8.5: «hver morgen kl. 07:00» (local time)
STARTUP_CHECK_MS: Final = 20_000
HEARD_MS: Final = 300  # audio check: this much speech on a mic counts as heard
LOUD_DB: Final = -3.0  # audio check: peaks above this are close to clipping
VOICED_DB: Final = -50.0  # after start: let the devices connect first
PROC_STALE_MS: Final = 10_000  # supervisor status older than this: the supervisor is gone


@dataclass
class SessionRecord:
    session: Session
    started_at: datetime
    ended_at: datetime | None = None


def _history_row(row: dict[str, Any]) -> dict[str, Any]:
    """Flat row for the technician's table and CSV. No card number exists to leak (I8)."""
    s = row["session"]
    rec = s.get("recording", {})
    show = s.get("show", {})
    return {
        "session_id": s["session_id"],
        "username": s["user"]["username"],
        "display_name": s["user"]["display_name"],
        "started_at": row["started_at"],
        "ended_at": row["ended_at"],
        "duration_s": rec.get("duration_s", 0),
        "recording": rec.get("state"),
        "started_by": rec.get("started_by"),
        "stopped_by": rec.get("stopped_by"),
        "participants": int(show.get("guests", 0)) + 1,
        "video": bool(show.get("video", True)),
        "publish": s.get("publish", {}).get("state"),
    }


def _why(exc: ValueError) -> str:
    """One readable line from a validation error, e.g. «T2_confirm_ms: Input should be …»."""
    if isinstance(exc, ValidationError):
        err = exc.errors()[0]
        return f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}"
    return str(exc).splitlines()[0]


Color = Literal["magenta", "cyan", "lilla", "oransje"]
PARTICIPANT_COLORS: Final[dict[str, Color]] = {
    "P1": "magenta",
    "P2": "cyan",
    "P3": "lilla",
    "P4": "oransje",
}

Role = Literal["touch", "operator", "admin"]


class AtemReader(Protocol):
    def multiview_readback(self) -> MultiviewReadback | None: ...


class Recorder(Protocol):
    """Pearl (spec 7.4). Start/stop are idempotent and asynchronous; ``state`` is polled."""

    state: RecordingStatus

    def start(self, now: int) -> bool: ...
    def stop(self, now: int) -> bool: ...
    def update(self, now: int) -> None: ...


class CommandError(Exception):
    """Not allowed now. The message is Norwegian and meant for the screen."""


@dataclass
class AlertRecord:
    id: int
    level: Literal["info", "warn", "error"]
    code: str
    message: str
    ts: datetime
    for_user: bool = False
    acknowledged: bool = False


@dataclass
class StudioDeps:
    site: Site
    show_types: ShowTypes
    presets: RulePresets
    clock: Clock
    executor: Executor
    recorder: Recorder
    store: Store | None = None
    simulator: bool = False
    log_dir: Path | None = None  # JSON-line logs, for the debug package
    atem: AtemReader | None = None  # atem-bridge client in studio; None: the executor reads
    system: System | None = None  # PC numbers for H-PC-*; None: no PC checks
    data_dir: Path = Path(".")  # the disk H-PC-1 watches
    cameras: CameraService | None = None  # PTZ cameras in core (CA-6); None: no H-CAM checks
    # Email alerts (HS-3): (smtp, to, subject, body), blocking. None: no email (simulator).
    send_mail: Callable[[SmtpConfig, list[str], str, str], None] | None = None


def _first_error(exc: Exception) -> str:
    """A validation error as one plain line for the screen."""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        first = errors()[0]
        return str(first.get("msg", exc)).removeprefix("Value error, ")
    return str(exc)


@dataclass
class Studio:
    deps: StudioDeps
    hub: Hub = field(default_factory=Hub)

    def __post_init__(self) -> None:
        self.sessions = SessionManager()
        self.show = self._show_for(self.sessions.default_show.participants)
        self.preset: RulesPreset = self.show.rules_preset
        self.features = self.show.features
        self.overrides: dict[str, float] = {}
        self.device_overrides: dict[str, str] = {}
        self.devices: Devices = self.deps.site.devices
        self.on_devices: Callable[[Devices], None] | None = None
        self.login_mode: LoginMode = "card" if self.deps.simulator else "open"
        self._autosaved_at = -1e9
        self.show_type: str = self.deps.show_types.default
        self._steps: list[SetupStep] | None = None  # setup helper, read on first use
        self._approved: dict[str, Approval] | None = None
        self._failed_seen: set[str] = set()  # switches already moved to shadow (F-1)
        self._had_session = False  # AT6
        self._iso_since: int | None = None  # when CutCut started ISO (engine ms)
        self._iso_file: str | None = None
        self._iso_by: str | None = None
        self._load_show_type()
        self._file_multiview = self.deps.site.multiview  # equipment/multiview_map.yaml
        self.multiview_in_app = False
        self.on_vision_map: Callable[[MultiviewMap], None] | None = None  # core: «vision.map»
        self._load_multiview()
        self.staff: Staff = self.deps.site.staff
        self.on_staff: Callable[[Staff], None] | None = None  # the API's sign-in list
        self._load_staff()
        self._load_devices()
        self._load_tuning()
        self._load_login_mode()
        engine = self._make_engine(self.show)
        self.runtime = CoreRuntime(
            engine,
            self.deps.clock,
            self.deps.executor,
            self.deps.store,
            on_decision=self._on_decision,
            on_step=self._on_step,
        )
        if self.deps.cameras is not None:
            self.runtime.camera_sink = self._camera_intent
            for cam, guard in self.deps.cameras.guards.items():
                guard.slow_zoom_ok = functools.partial(self._slow_zoom_allowed, cam)
        self.alerts: list[AlertRecord] = []
        clock = self.deps.clock
        self.notifier: Notifier | None = None
        send_mail = self.deps.send_mail
        if send_mail is not None:
            self.notifier = Notifier(
                lambda to, subject, body: send_mail(self.devices.alerts.smtp, to, subject, body),
                lambda: self.devices.alerts.email,
                self.devices.studio,
                mono_s=lambda: clock.mono_ms() / 1000,
                now=clock.now,
                red_after_s=self.devices.alerts.red_after_s,
                max_per_hour=self.devices.alerts.max_per_hour,
                on=lambda: self.devices.alerts.enabled,
            )
        self._regi_health: str | None = None
        self.health = HealthEngine(
            self._health_checks(),
            mono_s=lambda: clock.mono_ms() / 1000,
            now=clock.now,
            on_event=self._on_health,
        )
        self._processes: list[ProcessInfo] = []
        self._processes_at: int | None = None
        self.decisions: deque[dict[str, Any]] = deque(maxlen=LOG_KEEP)
        self.notice: str | None = None
        self.notice_until = 0
        self._alert_seq = 0
        self._last_state: dict[str, Any] = {}
        self._last_state_ms = -STATE_EVERY_MS
        self._last_meters_ms = -METERS_EVERY_MS
        self._tracked: tuple[str, TouchStep] | None = None
        self._started_ms = self.now
        self._mv_checked = False
        self.morning: MorningCheck | None = None
        self._morning_day: date | None = None
        self.local_tz: tzinfo | None = None  # None: the PC's own time zone
        self._mv_errors = ""
        self._mv_first_error: str | None = None
        self._mv_seen_error = False
        self.history: dict[str, SessionRecord] = {}
        self.mic_check: MicCheck | None = None
        self._touch_seen: int | None = None
        self._video_check = False
        self.on_vision_want: Callable[[], None] | None = None  # core: «vision.want» on the bus
        self._want_sent = -10_000
        self._pgm_apart_since: int | None = None
        self.on_audio_config: Callable[[dict[str, Any]], None] | None = None  # core: the bus
        self.runtime.on_audio = self._on_audio_frame
        self._check: dict[str, dict[str, int | bool]] = {}
        self._check_step: TouchStep = TouchStep.IDLE
        self._check_ms = self.now

    # -- configuration --------------------------------------------------------------------

    def _show_for(self, participants: int) -> ShowConfig:
        for show in self.deps.site.shows.values():
            if len(show.participants) == participants:
                return show
        raise CommandError(f"Studioet har ikke oppsett for {participants} personer.")

    def _merged(self, show: ShowConfig) -> ShowConfig:
        """The show with the technician's preset, switches and fine tuning applied."""
        return self._merged_with(show, self.preset, self.features, self.overrides)

    # -- show type (Innstillinger → Show-type, SE-6) ------------------------------------------

    def _type(self) -> ShowType:
        return self.deps.show_types.types[self.show_type]

    def _load_show_type(self) -> None:
        saved = self.deps.store.get_kv(SHOW_TYPE_KEY) if self.deps.store is not None else None
        if isinstance(saved, str) and saved in self.deps.show_types.types:
            self.show_type = saved
        self._default_show_for_type()

    def _default_show_for_type(self) -> None:
        """The show a new session starts with: the studio's type, and «Kun lyd» is audio."""
        d = self.sessions.default_show
        update: dict[str, Any] = {"type": self.show_type}
        if self._type().audio_only:
            update["video"] = False
        self.sessions.default_show = d.model_copy(update=update)

    def check_show_type(self, name: str) -> str:
        if name not in self.deps.show_types.types:
            known = ", ".join(self.deps.show_types.types)
            raise CommandError(f"Ukjent show-type «{name}». Velg en av: {known}.")
        return name

    def set_show_type(self, name: str, role: Role, actor: str) -> None:
        """The studio's show type (D-036: chosen in the setup, never by the user on touch)."""
        self._apply_show_type(self.check_show_type(name))
        self._audit(role, actor, "show_type", type=name)
        self._autosave()

    def _apply_show_type(self, name: str) -> None:
        self.show_type = name
        self._default_show_for_type()
        if self.deps.store is not None:
            self.deps.store.put_kv(SHOW_TYPE_KEY, name, self.deps.clock.now())

    def _start_with_type_preset(self) -> None:
        """A new session starts on the type's rules preset; fine tuning is kept, and the
        technician can still change the preset during the session."""
        preset = self._type().rules_preset
        if preset != self.preset:
            self.preset = preset
            self._save_tuning()
            self._reconfigure()
        for cam in self._type().ai_tracking:  # AT1: the show type asks for tracking
            try:
                self.set_tracking(CameraId(cam), True, "operator", "show-type")
            except (CommandError, ValueError) as exc:
                log.info("AI-tracking for %s fra show-typen ble ikke slått på: %s", cam, exc)

    def iso_wanted(self) -> bool:
        """The ATEM is to record ISO: set on the show or on the studio's type (spec 7.7)."""
        return self.show.iso_record or self._type().iso_record

    # -- setup helper (spec 8.4, HS-5/HS-6) -----------------------------------------------

    def setup_steps(self) -> list[SetupStep]:
        """The ten steps; a studio may replace one with ``site/<studio>/setup/NN-<id>.yaml``."""
        if self._steps is None:
            folders = [default_config_dir() / "defaults" / "setup", self.deps.site.root / "setup"]
            self._steps = load_steps(*folders)
        return self._steps

    def _setup_step(self, step_id: str) -> SetupStep:
        step = next((s for s in self.setup_steps() if s.id == step_id), None)
        if step is None:
            raise CommandError(f"Ukjent setup-steg «{step_id}».")
        return step

    def _approvals(self) -> dict[str, Approval]:
        """Kept in memory, read from the database once (the store writes in the background)."""
        if self._approved is None:
            saved = self.deps.store.get_kv(SETUP_KEY) if self.deps.store is not None else None
            self._approved = {}
            for k, v in (saved or {}).items() if isinstance(saved, dict) else ():
                try:
                    self._approved[str(k)] = Approval.model_validate(v)
                except ValidationError:
                    log.warning("godkjenning for setup-steg %s kan ikke leses", k)
        return self._approved

    def _fix_blocked(self, step: SetupStep) -> str | None:
        if step.fix is None:
            return None
        if self.sessions.recording:
            return "«Fiks for meg» er sperret mens opptak pågår."
        if step.fix.action == "atem_input_names":
            setter = getattr(self.deps.atem, "set_input_name", None)
            if not callable(setter) or self._atem_raw() is None:
                return "ATEM kan ikke leses nå. Sjekk at atem-bridge kjører."
        return None

    def _step_view(self, step: SetupStep, approvals: dict[str, Approval]) -> StepView:
        results = results_for(step, self.health.results())
        approved = approvals.get(step.id)
        blocked = self._fix_blocked(step)
        return StepView(
            step=step,
            state=step_state(step, results, approved),
            results=results,
            approved=approved,
            fix_available=step.fix is not None and blocked is None,
            fix_blocked=blocked,
        )

    def setup_view(self) -> list[StepView]:
        approvals = self._approvals()
        return [self._step_view(s, approvals) for s in self.setup_steps()]

    def setup_step_view(self, step_id: str) -> StepView:
        return self._step_view(self._setup_step(step_id), self._approvals())

    async def setup_check(self, step_id: str, role: Role, actor: str) -> StepView:
        """«Sjekk steget»: the step's health checks run at once. They only read (8.5)."""
        step = self._setup_step(step_id)
        await self.health.run_matching(step.matches)
        self._audit(role, actor, "setup_check", step=step.id)
        return self.setup_step_view(step.id)

    def setup_approve(self, step_id: str, role: Role, actor: str) -> StepView:
        """«Godkjent» with the technician's name and time. Refused while a check is red, or
        before the checks have answered."""
        view = self.setup_step_view(step_id)
        if view.state == "red":
            raise CommandError("Steget har feil som må rettes før det kan godkjennes.")
        if view.step.checks and view.state == "not_checked":
            raise CommandError("Trykk «Sjekk steget» først, så sjekkene har svart.")
        approvals = self._approvals()
        approvals[step_id] = Approval(by=actor, at=self.deps.clock.now())
        if self.deps.store is not None:
            data = {k: v.model_dump(mode="json") for k, v in approvals.items()}
            self.deps.store.put_kv(SETUP_KEY, data, self.deps.clock.now())
        self._audit(role, actor, "setup_approve", step=step_id, state=view.state)
        return self.setup_step_view(step_id)

    def setup_fix(self, step_id: str, role: Role, actor: str) -> StepView:
        """«Fiks for meg», after the technician confirmed. Never during a recording (8.4)."""
        step = self._setup_step(step_id)
        if step.fix is None:
            raise CommandError("Dette steget har ikke «Fiks for meg».")
        blocked = self._fix_blocked(step)
        if blocked is not None:
            raise CommandError(blocked)
        if step.fix.action == "atem_input_names":
            raw = self._atem_raw()
            current = {i.number: i.long for i in raw.inputs} if raw is not None else {}
            wanted = mv.atem_input_names(self.deps.site)
            changed = {n: name for n, name in wanted.items() if current.get(n) != name}
            setter = self.deps.atem.set_input_name  # type: ignore[union-attr]
            for number, name in changed.items():
                setter(number, name)
            self._audit(role, actor, "setup_fix", step=step.id, changed=changed)
        return self.setup_step_view(step.id)

    # -- technicians (Innstillinger → Teknikere) ---------------------------------------------

    def _load_staff(self) -> None:
        if self.deps.store is None:
            return
        saved = self.deps.store.get_kv(STAFF_KEY)
        if not isinstance(saved, dict):
            return
        try:
            self.staff = Staff.model_validate(saved)
        except ValueError as exc:
            log.warning("Lagret teknikerliste ble ikke brukt: %s", exc)

    def check_staff(self, operators: list[str], admins: list[str], actor: str) -> Staff:
        """The new list, or a plain message why not. Nobody can lock themselves out."""
        try:
            staff = Staff(operators=operators, admins=admins)
        except ValueError as exc:
            raise CommandError(_first_error(exc)) from exc
        if not staff.empty and not staff.admins:
            raise CommandError("Minst én må være admin, ellers kan ingen endre oppsettet.")
        if not staff.empty and actor not in staff.admins and actor != "simulator":
            raise CommandError(f"Du ({actor}) må stå som admin selv, ellers låser du deg ute.")
        return staff

    def set_staff(self, operators: list[str], admins: list[str], role: Role, actor: str) -> None:
        self._apply_staff(self.check_staff(operators, admins, actor))
        self._audit(role, actor, "staff", operators=operators, admins=admins)
        self._autosave()

    def _apply_staff(self, staff: Staff) -> None:
        self.staff = staff
        if self.on_staff is not None:
            self.on_staff(staff)
        if self.deps.store is not None:
            self.deps.store.put_kv(STAFF_KEY, staff.model_dump(mode="json"), self.deps.clock.now())

    def staff_info(self) -> dict[str, Any]:
        return {
            "operators": self.staff.operators,
            "admins": self.staff.admins,
            "first_setup": self.staff.empty,
        }

    def _load_login_mode(self) -> None:
        if self.deps.store is None:
            return
        saved = self.deps.store.get_kv(LOGIN_KEY)
        if saved in ("open", "card"):
            self.login_mode = saved

    def set_login_mode(self, mode: LoginMode, role: Role, actor: str) -> None:
        """«Innlogging» in the technician's settings (D-057). Card login needs the card reader
        and the card API; until they are set up, users start with the button on the screen."""
        if mode not in ("open", "card"):
            raise CommandError("Ukjent innlogging.")
        self._apply_login_mode(mode)
        self._audit(role, actor, "login_mode", mode=mode)
        self._autosave()

    def _apply_login_mode(self, mode: LoginMode) -> None:
        self.login_mode = mode
        if self.deps.store is not None:
            self.deps.store.put_kv(LOGIN_KEY, mode, self.deps.clock.now())

    def start_without_card(self, role: Role, actor: str) -> None:
        """«Start uten kort» on the touch screen: a session for «Gjest» (no Panopto owner)."""
        if self.login_mode != "open":
            raise CommandError("Bruk adgangskortet ditt, eller trykk Hjelp.")
        self.login(GUEST_USER, role, actor, source="guest")

    def _load_tuning(self) -> None:
        """Preset, switches and fine tuning survive a restart (the studio runs unattended)."""
        if self.deps.store is None:
            return
        saved = self.deps.store.get_kv(TUNING_KEY)
        if not isinstance(saved, dict):
            return
        try:
            self.preset, self.features, self.overrides = self._check_tuning(saved)
        except (ValueError, ConfigError) as exc:
            log.warning("Lagret tuning ble ikke brukt: %s", exc)

    def _check_tuning(
        self, saved: dict[str, Any]
    ) -> tuple[RulesPreset, Features, dict[str, float]]:
        preset = saved.get("preset", self.preset)
        features = self.features.model_copy(update=saved.get("features", {}))
        features = type(features).model_validate(features.model_dump())
        overrides = {str(k): float(v) for k, v in saved.get("overrides", {}).items()}
        effective_rules(
            self._merged_with(self.show, preset, features, overrides), self.deps.presets
        )
        return preset, features, overrides

    def _merged_with(
        self,
        show: ShowConfig,
        preset: RulesPreset,
        features: Features,
        overrides: dict[str, float],
    ) -> ShowConfig:
        data = show.model_dump()
        data.update(
            rules_preset=preset,
            features=features.model_dump(),
            rules_override={**show.rules_override, **overrides},
        )
        # Camera addresses come from the equipment settings, which the technician can change.
        for cid, cam in data["cameras"].items():
            device = self.devices.cameras.get(cid)
            if device is not None and device.ip is not None:
                cam["ip"] = device.ip
        return ShowConfig.model_validate(data)

    def _inputs(self) -> dict[str, int]:
        """ATEM input per tile key. The current show wins; other shows fill in seats that are
        empty now, so the technician sees the right «Camera n» for every seat."""
        out: dict[str, int] = {}
        for show in [*self.deps.site.shows.values(), self.show]:
            for p in show.participants:
                cam = show.cameras.get(p.camera)
                if cam is not None:
                    out[p.id.value] = cam.atem_input
            for cam in show.cameras.values():
                if cam.role in ("bird", "wide"):
                    out[cam.role.upper()] = cam.atem_input
            out["CONTENT"] = show.content.atem_input
        return out

    # -- equipment addresses (Oppsett → Utstyr og nettverk) ----------------------------------

    def _load_devices(self) -> None:
        if self.deps.store is None:
            return
        saved = self.deps.store.get_kv(devices.DEVICES_KEY)
        if not isinstance(saved, dict):
            return
        overrides = {str(k): str(v) for k, v in saved.items()}
        try:
            self.devices = devices.apply(self.deps.site.devices, overrides)
        except devices.DeviceSettingsError as exc:
            log.warning("Lagrede utstyrsadresser ble ikke brukt: %s", exc)
            return
        self.device_overrides = overrides

    def set_devices(self, changes: dict[str, str | None], role: Role, actor: str) -> None:
        """Change equipment addresses. ``None`` goes back to the value in devices.yaml. Applies
        from the next connection; nothing changes if any value is invalid."""
        updated = dict(self.device_overrides)
        for key, value in changes.items():
            if value is None or value == "":
                updated.pop(key, None)
            else:
                updated[key] = value.strip()
        effective = self._check_devices(updated)
        self._apply_devices(updated, effective)
        self._audit(role, actor, "devices", **{k: v for k, v in changes.items()})
        self._autosave()

    def _check_devices(self, overrides: dict[str, str]) -> Devices:
        try:
            return devices.apply(self.deps.site.devices, overrides)
        except devices.DeviceSettingsError as exc:
            raise CommandError(str(exc)) from exc

    def _apply_devices(self, updated: dict[str, str], effective: Devices) -> None:
        self.device_overrides, self.devices = updated, effective
        if self.on_devices is not None:
            self.on_devices(effective)  # e.g. point the Companion and Pearl clients elsewhere
        if self.deps.store is not None:
            self.deps.store.put_kv(devices.DEVICES_KEY, updated, self.deps.clock.now())
        self._reconfigure()

    def devices_info(self) -> dict[str, Any]:
        return {
            "studio": self.devices.studio,
            "atem_model": self.devices.atem.model,
            "rows": devices.rows(self.deps.site.devices, self.devices, self.device_overrides),
        }

    # -- ISO recording on the ATEM's disk (spec 7.7, DA-8) -------------------------------

    def _iso(self) -> IsoRecorder | None:
        for src in (self.deps.atem, self.deps.executor):
            if src is not None and callable(getattr(src, "iso_start", None)):
                return src  # type: ignore[return-value]
        return None

    def _iso_status(self) -> IsoStatus | None:
        rec = self._iso()
        return rec.iso_status() if rec is not None else None

    def _iso_running(self) -> bool:
        st = self._iso_status()
        return st is not None and st.recording

    def iso_info(self) -> IsoInfo:
        st = self._iso_status()
        if st is not None and not st.recording and self._iso_since is not None:
            self._iso_since = None  # stopped on the ATEM itself, or by us
        running = self._iso_since is not None
        return IsoInfo(
            available=st is not None,
            state=st.state if st is not None else "unknown",
            disk=st.disk if st is not None else None,
            time_available_s=round(st.time_available_s)
            if st is not None and st.time_available_s is not None
            else None,
            error=st.error if st is not None else None,
            filename=self._iso_file,
            duration_s=(self.now - self._iso_since) // 1000 if running and self._iso_since else 0,
            started_by=self._iso_by,
            wanted=self.iso_wanted(),
        )

    def iso_start(self, role: Role, actor: str) -> None:
        """Start ISO recording of every input, under the session's name (7.7)."""
        rec = self._iso()
        st = rec.iso_status() if rec is not None else None
        if rec is None or st is None:
            raise CommandError("ATEM kan ikke leses nå. Sjekk at atem-bridge kjører.")
        if st.recording:
            raise CommandError("ISO-opptaket går allerede.")
        if not st.disk:
            raise CommandError("Det er ingen disk i ATEM for ISO-opptak.")
        session = self.sessions.session
        name = iso.filename(
            self.deps.clock.now(),
            session.show.type if session else self.show_type,
            session.user.username if session else None,
        )
        if not rec.iso_start(name):
            raise CommandError("ATEM tok ikke imot kommandoen. Prøv igjen.")
        self._iso_since, self._iso_file, self._iso_by = self.now, name, actor
        self._audit(role, actor, "iso_start", filename=name)

    def iso_stop(self, role: Role, actor: str) -> None:
        """Stop ISO. Only ever because a person asked (I7)."""
        rec = self._iso()
        st = rec.iso_status() if rec is not None else None
        if rec is None or st is None:
            raise CommandError("ATEM kan ikke leses nå. Sjekk at atem-bridge kjører.")
        if not st.recording:
            raise CommandError("ISO-opptaket går ikke.")
        if not rec.iso_stop():
            raise CommandError("ATEM tok ikke imot kommandoen. Prøv igjen.")
        self._iso_since = None
        self._audit(role, actor, "iso_stop", filename=self._iso_file)

    def _iso_with_pearl(self) -> None:
        """The show type (or show) records ISO: start it with Pearl. A failure never stops the
        Pearl recording; the technician is told."""
        if self._iso_running():
            return
        try:
            self.iso_start("operator", "automatisk (show-type)")
        except CommandError as exc:
            self._alert("warn", "H-ATEM-4", f"ISO-opptaket startet ikke: {exc}")

    def _recording_info(self) -> RecordingInfo:
        session = self.sessions.session
        info = RecordingInfo(
            pearl=self.deps.recorder.state.value,
            duration_s=session.recording.duration_s if session else 0,
            started_by=session.recording.started_by if session else None,
            iso=self.iso_info(),
        )
        status = getattr(self.deps.recorder, "status", None)
        if not callable(status):
            return info
        st = status()
        main = next((x for x in st.storages if x.id == "main"), None)
        return info.model_copy(
            update={
                "online": st.online,
                "error": st.last_error,
                "firmware": st.firmware,
                "storage_free_pct": round(main.free_share * 100) if main else None,
            }
        )

    def _save_tuning(self) -> None:
        if self.deps.store is not None:
            value = {
                "preset": self.preset,
                "features": self.features.model_dump(),
                "overrides": self.overrides,
            }
            self.deps.store.put_kv(TUNING_KEY, value, self.deps.clock.now())
        self._autosave(throttle_s=60)

    def _make_engine(self, show: ShowConfig) -> Engine:
        merged = self._merged(show)
        rules = effective_rules(merged, self.deps.presets)
        return Engine(
            EngineConfig.from_show(merged, rules),
            now_ms=self.deps.clock.mono_ms(),
            wall_clock=self.deps.clock.now(),
        )

    def _rebuild_engine(self) -> None:
        settings = self.runtime.engine.settings()
        engine = self._make_engine(self.show)
        engine.auto, engine.lock = settings["auto"], settings["lock"]
        engine.content_enabled, engine.shadow = settings["content_enabled"], settings["shadow"]
        self.runtime.engine = engine

    @property
    def engine(self) -> Engine:
        return self.runtime.engine

    @property
    def now(self) -> int:
        return self.deps.clock.mono_ms()

    # -- the loop -------------------------------------------------------------------------

    def tick(self) -> StepResult:
        now = self.now
        self.apply(self.sessions.tick(now))
        self.deps.recorder.update(now)
        self.apply(self.sessions.pearl_status(self.deps.recorder.state, now))
        result = self.runtime.tick()
        if self.notice and now >= self.notice_until:
            self.notice = None
        if now - self._last_meters_ms >= METERS_EVERY_MS:
            self._last_meters_ms = now
            self.hub.publish("meters", {k: m.model_dump() for k, m in self.meters().items()})
        if now - self._last_state_ms >= STATE_EVERY_MS:
            self._last_state_ms = now
            self._publish_state()
        self._track_session()
        self._tracking_off_after_session()
        self._switches_failed()
        self._audio_check(now)
        self._maybe_add_video_check()
        if not self._mv_checked and (
            self._mv_readback() is not None or now - self._started_ms >= MULTIVIEW_STARTUP_WAIT_MS
        ):
            self._mv_checked = True
            self._check_multiview()
        return result

    # -- setup step 5: the microphones (AU-7) --------------------------------------------------

    def _studio_mics(self) -> list[MicId]:
        mics = {p.mic for show in self.deps.site.shows.values() for p in show.participants}
        return sorted(mics, key=lambda m: m.value)

    def _mic_check(self) -> MicCheck:
        if self.mic_check is None:
            self.mic_check = MicCheck(self._studio_mics())
        return self.mic_check

    def _on_audio_frame(self, mics: dict[MicId, MicFrame]) -> None:
        if self.mic_check is not None and self.mic_check.running is not None:
            self.mic_check.feed({m: f.level_db for m, f in mics.items()}, self.now)

    def mic_check_status(self) -> dict[str, Any]:
        status = self._mic_check().status(self.now)
        status["saved"] = self.deps.site.baseline.audio.model_dump(mode="json")
        status["simulator"] = self.deps.simulator
        return status

    def mic_check_start(self, what: str, role: Role, actor: str) -> dict[str, Any]:
        if self.sessions.recording:
            raise CommandError("Mic-sjekken kan ikke kjøres under opptak.")
        check = self._mic_check()
        if what == "noise":
            check.start_noise(self.now)
        else:
            try:
                check.start_talk(MicId(what), self.now)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
        self._audit(role, actor, "mic_check", what=what)
        return self.mic_check_status()

    def mic_check_reset(self, role: Role, actor: str) -> None:
        self.mic_check = None
        self._audit(role, actor, "mic_check_reset")

    def mic_check_save(self, role: Role, actor: str) -> dict[str, Any]:
        """Approve: write baseline.yaml and give audio-capture the new leakage at once."""
        check = self._mic_check()
        if not check.results:
            raise CommandError("Mål minst én mikrofon først.")
        wrong = [r.mic.value for r in check.results.values() if not r.right_channel]
        if wrong:
            raise CommandError(f"Feil kanal på {', '.join(wrong)}. Rett det og mål på nytt.")
        site = self.deps.site
        new = check.baseline(site.baseline, actor, self.deps.clock.now())
        self._apply_baseline(new)
        self._audit(role, actor, "mic_check_save", mics=sorted(r.value for r in check.results))
        self._autosave()
        self._alert("info", "SETUP-5", f"Mikrofonene er målt og lagret som fasit av {actor}.")
        return self.mic_check_status()

    def _apply_baseline(self, new: Baseline) -> None:
        site = self.deps.site
        if not self.deps.simulator:  # the simulator runs on files in the repo: never write
            write_baseline(site.root / "baseline.yaml", new)
        self.deps.site = site.model_copy(update={"baseline": new})
        if self.on_audio_config is not None:
            leak = {
                s.value: {d.value: v for d, v in row.items()}
                for s, row in new.audio.leak_db.items()
            }
            self.on_audio_config({"leak_db": leak})

    # -- «Lagre oppsett» / «Hent oppsett» (everything entered in the app) ---------------------

    def setup_export(self) -> setup_file.SetupFile:
        return setup_file.SetupFile(
            studio=self.devices.studio,
            exported=self.deps.clock.now(),
            cutcut=__version__,
            devices=devices.values(self.devices),
            staff=self.staff,
            login_mode=self.login_mode,
            show_type=self.show_type,
            tuning=setup_file.Tuning(
                preset=self.preset,
                features=self.features.model_dump(),
                overrides=self.overrides,
            ),
            baseline=self.deps.site.baseline,
            multiview=self.deps.site.multiview if self.multiview_in_app else None,
        )

    def setup_import(self, text: str, role: Role, actor: str, *, apply: bool) -> list[str]:
        """Check a setup file, and with ``apply`` use it. Everything is checked before anything
        changes. Returns what is (or would be) changed, in plain words."""
        try:
            f = setup_file.parse(text)
        except setup_file.SetupFileError as exc:
            raise CommandError(str(exc)) from exc
        changes: list[str] = []
        if f.studio != self.devices.studio:
            changes.append(f"Fra et annet studio: {f.studio} (dette er {self.devices.studio})")
        dev: tuple[dict[str, str], Devices] | None = None
        if f.devices is not None:
            base = devices.values(self.deps.site.devices)
            overrides = {k: v for k, v in f.devices.items() if v != base.get(k)}
            dev = (overrides, self._check_devices(overrides))
            now = devices.values(self.devices)
            diff = [k for k, v in devices.values(dev[1]).items() if now.get(k) != v]
            changes.append(
                f"Utstyr og varsling: {len(diff)} endret"
                + (f" ({', '.join(diff)})" if diff else "")
            )
        staff: Staff | None = None
        if f.staff is not None:
            if self.staff.empty:  # first setup: the file decides who the technicians are
                staff = f.staff
            else:
                staff = self.check_staff(f.staff.operators, f.staff.admins, actor)
            changes.append(
                f"Teknikere: {len(staff.operators)} operatører, {len(staff.admins)} admin"
            )
        tuning: tuple[RulesPreset, Features, dict[str, float]] | None = None
        if f.tuning is not None:
            try:
                tuning = self._check_tuning(f.tuning.model_dump())
            except (ValueError, ConfigError) as exc:
                raise CommandError(f"Regelinnstillingene i filen kan ikke brukes: {exc}") from exc
            changes.append(f"Regler: {tuning[0]}, {len(tuning[2])} finjusteringer")
        if f.show_type is not None:
            self.check_show_type(f.show_type)
            changes.append(f"Show-type: {self.deps.show_types.types[f.show_type].name}")
        if f.login_mode is not None:
            changes.append(
                f"Innlogging: {'Start-knapp' if f.login_mode == 'open' else 'Adgangskort'}"
            )
        if f.baseline is not None and f.baseline.approved_at is not None:
            changes.append(
                f"Mikrofon-fasit fra {f.baseline.approved_at:%Y-%m-%d} ({f.baseline.approved_by})"
            )
        mv_map: MultiviewMap | None = None
        if f.multiview is not None:
            mv_map = self.check_multiview_map(f.multiview.model_dump(mode="json"))
            changes.append(f"Rutekart for multiview ({mv_map.layout})")
            if apply and self.sessions.recording:
                raise CommandError("Rutekartet kan ikke endres mens opptak pågår.")
        if not apply:
            return changes
        if mv_map is not None and self.deps.store is not None:
            self.deps.store.put_kv(MV_KEY, mv_map.model_dump(mode="json"), self.deps.clock.now())
        if mv_map is not None:
            self._use_multiview(mv_map)
        if dev is not None:
            self._apply_devices(*dev)
        if staff is not None:
            self._apply_staff(staff)
        if tuning is not None:
            self.preset, self.features, self.overrides = tuning
            self._save_tuning()
            self._reconfigure()
        if f.login_mode is not None:
            self._apply_login_mode(f.login_mode)
        if f.show_type is not None:
            self._apply_show_type(f.show_type)
        if f.baseline is not None and f.baseline.approved_at is not None:
            self._apply_baseline(f.baseline)
        self._audit(role, actor, "setup_import", studio=f.studio, changes=changes)
        self._alert("info", "OPPSETT", f"Oppsett hentet inn av {actor}: " + "; ".join(changes))
        self._autosave()
        return changes

    def _autosave(self, throttle_s: float = 0.0) -> None:
        """A copy of the setup in data\\oppsett\\ on the PC after every change."""
        if self.deps.store is None or self.deps.simulator:
            return
        now = self.deps.clock.mono_ms() / 1000
        if throttle_s and now - self._autosaved_at < throttle_s:
            return
        self._autosaved_at = now
        try:
            setup_file.autosave(
                self.deps.data_dir / "oppsett", self.setup_export(), self.deps.clock.now()
            )
        except OSError as exc:  # a full disk must not stop a change from taking effect
            log.warning("Kopi av oppsettet ble ikke skrevet: %s", exc)

    # -- audio check during the countdown (AU-7) ------------------------------------------------

    def _audio_check(self, now: int) -> None:
        """While 3-2-1 counts down, note who was heard, who is muted on the mixer, who is too
        loud. The seat map shows it live; when recording starts, the result is reported."""
        step = self.sessions.step
        dt, self._check_ms = now - self._check_ms, now
        if step is TouchStep.COUNTDOWN and self._check_step is not TouchStep.COUNTDOWN:
            self._check = {
                p.id.value: {"ms": 0, "muted": False, "loud": False} for p in self.show.participants
            }
        if step is TouchStep.COUNTDOWN:
            frames = self.runtime.latest_mics
            for p in self.show.participants:
                f = frames.get(p.mic)
                c = self._check.get(p.id.value)
                if f is None or c is None:
                    continue
                voiced = f.vad >= 0.5 and f.level_db > VOICED_DB and not f.leak
                if voiced:
                    c["ms"] = int(c["ms"]) + dt
                    if not f.in_main_mix:
                        c["muted"] = True
                if f.level_db > LOUD_DB:
                    c["loud"] = True
        elif self._check_step is TouchStep.COUNTDOWN and step is TouchStep.REC:
            self._report_audio_check()
        self._check_step = step

    def audio_check_info(self) -> list[SeatAudio]:
        return [
            SeatAudio(
                id=pid,
                heard=int(c["ms"]) >= HEARD_MS,
                muted=bool(c["muted"]),
                loud=bool(c["loud"]),
            )
            for pid, c in self._check.items()
        ]

    def _report_audio_check(self) -> None:
        names = {p.id.value: p.name for p in self.show.participants}
        faders = {p.id.value: p.mic.value[1:] for p in self.show.participants}  # M2 = fader 2
        info = self.audio_check_info()
        muted = [s for s in info if s.muted]
        if muted:
            who = ", ".join(names[s.id] for s in muted)
            which = ", ".join(faders[s.id] for s in muted)
            self.notice = f"{who}: mikrofonen er skrudd ned på mikseren. Skyv fader {which} opp."
            self.notice_until = self.now + 8_000
            self.hub.publish("touch", {"notice": self.notice})
        parts = []
        silent = [names[s.id] for s in info if not s.heard and not s.muted]
        if silent:
            parts.append("ikke hørt: " + ", ".join(silent))
        if muted:
            parts.append("dempet på mikseren: " + ", ".join(names[s.id] for s in muted))
        loud = [names[s.id] for s in info if s.loud]
        if loud:
            parts.append("for høyt (nær klipping): " + ", ".join(loud))
        if parts:
            level: Literal["info", "warn"] = "warn" if muted else "info"
            self._alert(level, "LYDSJEKK", "Lydsjekk: " + "; ".join(parts))
        else:
            log.info("Lydsjekk: alle hørt", extra={"check": "LYDSJEKK"})

    # -- multiview (D-055) ---------------------------------------------------------------

    def _mv_readback(self) -> MultiviewReadback | None:
        source: object = self.deps.atem if self.deps.atem is not None else self.deps.executor
        reader = getattr(source, "multiview_readback", None)
        return reader() if callable(reader) else None

    # -- health (spec 8.5, HS-1) -------------------------------------------------------------

    def _on_health(self, ev: HealthEvent) -> None:
        """An issue opens or changes: an alert. It closes (30 s green): its alerts go away."""
        r = ev.result
        if ev.kind == "resolved":
            if self.notifier is not None:
                self.notifier.on_health(ev)
            for a in self.alerts:
                if a.code == r.id:
                    a.acknowledged = True
            return
        if self.notifier is not None:
            self.notifier.on_health(ev)
        level: Literal["warn", "error"] = "error" if r.status == "red" else "warn"
        # The touch screen reads the live check (state.health), not the alert, so the user is
        # not held back during the 30 s the technician's issue stays open after a fix.
        self._alert(level, r.id, r.message, log_it=False)

    def _health_checks(self) -> list[HealthCheck]:
        clock = self.deps.clock
        now = clock.now
        self._proc_checks: set[str] = set()
        checks: list[HealthCheck] = [
            health_checks.audio_stream(
                self.runtime.audio_age_ms, now, lambda: self.runtime.audio_status
            ),
            health_checks.pearl(self._pearl_reading, now),
            health_checks.atem(
                lambda: self.runtime.atem is not None,
                lambda: (clock.mono_ms() - self._started_ms) / 1000,
                now,
            ),
            health_checks.companion(
                self._companion_reading, self.devices.companion.pages_version, now
            ),
            health_checks.atem_macros(self._atem_macros, now),
        ]
        system = self.deps.system
        if system is not None:
            checks += health_checks.pc(lambda: system.snapshot(self.deps.data_dir), now)
            checks += health_checks.network(
                system.interfaces, lambda: str(self.devices.atem.ip), now
            )
        if self.notifier is not None:
            checks.append(health_checks.alert_mail(self.alerts_info, now))
        source: object = self.deps.atem if self.deps.atem is not None else self.deps.executor
        if callable(getattr(source, "raw", None)):  # an ATEM that is read (not the simulator)
            checks.append(health_checks.atem_setup(self._atem_setup_reading, now))
            checks.append(health_checks.atem_iso(self._iso_reading, now))
        cams = self.deps.cameras
        if cams is not None and cams.guards:
            for cam in sorted(cams.guards, key=lambda c: c.value):
                checks.append(
                    health_checks.camera(f"H-CAM-{cam.value}", self._camera_reading(cam), now)
                )
            checks.append(
                health_checks.camera_move(
                    lambda: [self._camera_reading(c)() for c in list(cams.guards)], now
                )
            )
        return checks

    def camera_name(self, cam: CameraId) -> str:
        """«Camera 2», by the ATEM input as on the screens."""
        for show in [self.show, *self.deps.site.shows.values()]:
            c = show.cameras.get(cam)
            if c is not None:
                return f"Camera {c.atem_input}"
        return cam.value

    def _camera_reading(self, cam: CameraId) -> Callable[[], health_checks.CameraReading]:
        def read() -> health_checks.CameraReading:
            svc = self.deps.cameras
            g = svc.guards.get(cam) if svc is not None else None
            name = self.camera_name(cam)
            if svc is None or g is None:
                return health_checks.CameraReading(name, read=False, online=False, steered=False)
            t = svc.clock()
            st = g.st
            moved = svc.unexpected.get(cam)
            return health_checks.CameraReading(
                name=name,
                read=st.status is not None,
                online=bool(st.status and st.status.online),
                steered=st.ok,
                mode=st.status.mode if st.status else "",
                answer_ms=st.answer_ms,
                last_error=st.last_error,
                since_start_s=t - svc.started if svc.started is not None else 0.0,
                moved_by_itself_s=None if moved is None else t - moved,
            )

        return read

    def _atem_raw(self) -> AtemStateRaw | None:
        source: object = self.deps.atem if self.deps.atem is not None else self.deps.executor
        raw_fn = getattr(source, "raw", None)
        raw = raw_fn() if callable(raw_fn) else None
        return raw if isinstance(raw, AtemStateRaw) else None

    def _atem_setup_reading(self) -> health_checks.AtemSetupReading:
        raw = self._atem_raw()
        fasit = self.deps.site.baseline.atem
        if raw is None:
            return health_checks.AtemSetupReading(read=False)
        return health_checks.AtemSetupReading(
            read=True,
            video_mode=raw.multiview.video_mode if raw.multiview else None,
            input_names={i.number: i.long for i in raw.inputs},
            aux=list(raw.aux),
            multiview_changed=self._mv_first_error,
            fasit_video_mode=fasit.video_mode if fasit else "1080p50",
            fasit_input_names=dict(fasit.input_names) if fasit else None,
            fasit_aux=list(fasit.aux) if fasit else None,
        )

    def _iso_reading(self) -> health_checks.IsoReading:
        raw = self._atem_raw()
        if raw is None:
            return health_checks.IsoReading(read=False, wanted=self.iso_wanted())
        iso = raw.iso
        if iso is None:
            return health_checks.IsoReading(read=True, wanted=self.iso_wanted())
        return health_checks.IsoReading(
            read=True,
            wanted=self.iso_wanted(),
            state=iso.state,
            error=iso.error,
            time_available_s=iso.time_available_s,
            disk=iso.disk,
            disk_status=iso.disk_status,
        )

    def save_atem_baseline(self, role: Role, actor: str) -> dict[str, Any]:
        """«Lagre ATEM som fasit»: format, input names and AUX as they are now (H-ATEM-2)."""
        raw = self._atem_raw()
        if raw is None:
            raise CommandError("ATEM kan ikke leses nå. Sjekk at atem-bridge kjører.")
        fasit = AtemBaseline(
            video_mode=raw.multiview.video_mode if raw.multiview else "1080p50",
            input_names={i.number: i.long for i in raw.inputs},
            aux=list(raw.aux),
            approved_by=actor,
            approved_at=self.deps.clock.now(),
        )
        self._apply_baseline(self.deps.site.baseline.model_copy(update={"atem": fasit}))
        self._audit(role, actor, "atem_baseline", video_mode=fasit.video_mode)
        self._autosave()
        return self.atem_status()

    def atem_status(self) -> dict[str, Any]:
        """What CutCut reads from the ATEM, in ATEM terms (setup screen, machine test DA-5)."""
        source: object = self.deps.atem if self.deps.atem is not None else self.deps.executor
        raw_fn = getattr(source, "raw", None)
        status_fn = getattr(source, "status", None)
        raw = raw_fn() if callable(raw_fn) else None
        st = status_fn() if callable(status_fn) else None
        macros = self._atem_macros()
        rb = self.runtime.atem
        return {
            "connected": raw is not None if callable(raw_fn) else rb is not None,
            "model": getattr(st, "model", None),
            "last_error": getattr(st, "last_error", None),
            "program_input": raw.program_input if raw else None,
            "preview_input": raw.preview_input if raw else None,
            "program": rb.program.value if rb else None,
            "preview": rb.preview.value if rb else None,
            "video_mode": raw.multiview.video_mode if raw and raw.multiview else None,
            "recording": raw.recording if raw else None,
            "macros": {str(k): v for k, v in sorted((macros or {}).items())},
            "macro_problems": macro_check(macros) if macros is not None else [],
            "inputs": {str(i.number): i.long for i in raw.inputs} if raw else {},
            "aux": list(raw.aux) if raw else [],
            "iso": raw.iso.model_dump() if raw and raw.iso else None,
            "fasit": self.deps.site.baseline.atem.model_dump(mode="json")
            if self.deps.site.baseline.atem
            else None,
        }

    def _atem_macros(self) -> dict[int, str] | None:
        source: object = self.deps.atem if self.deps.atem is not None else self.deps.executor
        read = getattr(source, "macros", None)
        return read() if callable(read) else None

    def _pearl_reading(self) -> health_checks.PearlReading:
        rec = self.deps.recorder
        status = getattr(rec, "status", None)
        if callable(status):  # PearlRecorder (studio)
            st = status()
            main = next((x for x in st.storages if x.id == "main"), None)
            return health_checks.PearlReading(
                st.online, st.last_error, main.free_bytes if main else None
            )
        minutes = getattr(rec, "storage_minutes", None)  # FakePearl (simulator)
        free = None
        if isinstance(minutes, int):
            free = int(minutes * 60 * health_checks.PEARL_MBPS * 1e6 / 8)
        return health_checks.PearlReading(bool(getattr(rec, "online", True)), None, free)

    def _companion_reading(self) -> health_checks.CompanionReading:
        """Runs in a worker thread (it may wait on Companion's HTTP API)."""
        ex = self.deps.executor
        api = getattr(ex, "api", None)
        if api is not None and hasattr(api, "pages_version"):  # CompanionExecutor (studio)
            try:
                version = api.pages_version()
            except Exception as exc:
                return health_checks.CompanionReading(False, error=type(exc).__name__)
            return health_checks.CompanionReading(True, version, pages_read=True)
        return health_checks.CompanionReading(bool(getattr(ex, "companion_online", True)))

    def health_info(self) -> HealthInfo:
        return HealthInfo(
            status=self.health.overall(), checks=self.health.results(), morning=self.morning
        )

    async def health_loop(self, every_s: float = 0.25) -> None:
        """The checks on their intervals, plus the start-up and morning check (HS-4)."""
        while True:
            try:
                await self.health.step()
                self._publish_regi_health()
                if self.notifier is not None:
                    await self.notifier.tick()
                await self._maybe_morning_check()
            except Exception:  # health must never take core down
                log.exception("helsesjekkene feilet")
            await asyncio.sleep(every_s)

    def _publish_regi_health(self) -> None:
        """Companion's ``regi_health`` follows the worst open issue (a Stream Deck button)."""
        value = {"green": "ok", "yellow": "warn", "red": "error"}[self.health.overall()]
        if value != self._regi_health:
            self._regi_health = value
            self.deps.executor.submit(SetCompanionVariable("regi_health", value))

    # -- alerts outside the studio (HS-3) ----------------------------------------------------

    def alerts_info(self) -> dict[str, Any]:
        a, n = self.devices.alerts, self.notifier
        return {
            "on": a.enabled,
            "email": a.email,
            "smtp_host": a.smtp.host,
            "red_after_s": a.red_after_s,
            "enabled": n is not None and a.enabled and bool(a.email) and bool(a.smtp.host),
            "sent": n.sent if n else 0,
            "last_sent": n.last_sent.isoformat() if n and n.last_sent else None,
            "last_error": n.last_error if n else None,
            "support_email": self.devices.support.email,
        }

    async def test_alert(self, role: Role, actor: str) -> list[str]:
        """«Send testvarsel»: one email now, so the technician knows it arrives."""
        send = self.deps.send_mail
        a = self.devices.alerts
        if send is None:
            raise CommandError("E-postvarsel finnes ikke i simulatoren.")
        if not a.email:
            raise CommandError("Skriv inn minst én e-postadresse først.")
        subject = f"[CutCut {self.devices.studio}] Testvarsel"
        body = (
            f"Dette er et testvarsel fra CutCut i {self.devices.studio}, sendt av {actor}.\n"
            f"Varsler sendes når noe har vært rødt i over {a.red_after_s:.0f} s, og med en gang "
            "når et opptak ikke starter eller stopper av seg selv."
        )
        self._audit(role, actor, "alerts.test", to=", ".join(a.email))
        try:
            await asyncio.to_thread(send, a.smtp, a.email, subject, body)
        except Exception as e:
            if self.notifier is not None:
                self.notifier.last_error = str(e)
            raise CommandError(str(e) or "Testvarselet ble ikke sendt.") from e
        if self.notifier is not None:
            self.notifier.last_error, self.notifier.last_sent = None, self.deps.clock.now()
        return a.email

    def _local_now(self) -> datetime:
        return self.deps.clock.now().astimezone(self.local_tz)

    async def _maybe_morning_check(self) -> None:
        local = self._local_now()
        if self.morning is None:
            if self.now - self._started_ms >= STARTUP_CHECK_MS:
                await self.morning_check("oppstart")
            return
        if local.hour >= MORNING_HOUR and self._morning_day != local.date():
            await self.morning_check("morgen")

    async def morning_check(
        self, reason: Literal["oppstart", "morgen", "manuell"] = "manuell"
    ) -> MorningCheck:
        """Run the whole catalogue now, and the multiview check (D-056)."""
        self._check_multiview()
        results = await self.health.run_all()
        rank = {"green": 0, "yellow": 1, "red": 2}
        bad = sorted((r for r in results if r.status != "green"), key=lambda r: -rank[r.status])
        status: Literal["green", "yellow", "red"] = bad[0].status if bad else "green"
        if self._mv_errors:
            status = "red" if status == "red" else "yellow"
        local = self._local_now()
        if local.hour >= MORNING_HOUR:
            self._morning_day = local.date()  # a start after 07:00 is today's morning check
        failed = [r.id for r in bad] + (["H-MV"] if self._mv_errors else [])
        self.morning = MorningCheck(
            ts=local.isoformat(timespec="seconds"), reason=reason, status=status, failed=failed
        )
        text = "alt grønt" if not failed else ", ".join(failed)
        log.info("Morgensjekk (%s): %s", reason, text, extra={"check": "HS-4"})
        return self.morning

    # -- processes (supervisor, SO-1) ------------------------------------------------------

    def on_supervisor(self, payload: dict[str, Any]) -> None:
        """``supervisor.status`` from the bus: remember it; ``H-PROC-<name>`` checks read it.

        A check is added for each process the first time the supervisor reports it."""
        procs: list[ProcessInfo] = []
        fields = ProcessInfo.model_fields
        for raw in payload.get("processes") or []:
            try:
                procs.append(ProcessInfo.model_validate({k: raw[k] for k in fields if k in raw}))
            except (ValueError, TypeError):
                continue
        first = self._processes_at is None
        self._processes, self._processes_at = procs, self.deps.clock.mono_ms()
        now = self.deps.clock.now
        if first:
            self.health.add(health_checks.supervisor(self._supervisor_age_ms, now))
        for p in procs:
            if f"H-PROC-{p.name}" not in self._proc_checks:
                self._proc_checks.add(f"H-PROC-{p.name}")
                self.health.add(health_checks.process(p.name, self._process_reading(p.name), now))

    def _supervisor_age_ms(self) -> int:
        at = self._processes_at
        return 0 if at is None else self.deps.clock.mono_ms() - at

    def _process_reading(self, name: str) -> Callable[[], health_checks.ProcessReading | None]:
        def read() -> health_checks.ProcessReading | None:
            if self._supervisor_age_ms() > PROC_STALE_MS:
                return None  # the supervisor is gone; H-PROC-supervisor says so
            p = next((x for x in self._processes if x.name == name), None)
            if p is None:
                return None
            return health_checks.ProcessReading(p.name, p.running, p.restarts_10min, p.last_reason)

        return read

    def processes_info(self) -> list[ProcessInfo]:
        if self._processes_at is None:
            return []
        if self.deps.clock.mono_ms() - self._processes_at > PROC_STALE_MS:
            return [ProcessInfo(name="supervisor", running=False, last_reason="ingen status")]
        return list(self._processes)

    def multiview_status(self) -> dict[str, Any]:
        """Rutekart, what the ATEM shows, the recommended layout, and what is wrong."""
        site = self.deps.site
        studio_inputs = mv.StudioInputs.from_site(site)
        rec = mv.recommended(studio_inputs, self.devices.atem.model)
        readback = self._mv_readback()
        findings = mv.check_map(site.multiview, studio_inputs)
        suggestions: list[mv.Finding] = []
        if site.multiview is not None:
            findings += mv.check_readback(site.multiview, readback)
            suggestions = mv.compare_recommended(site.multiview, rec)
        return {
            "map": site.multiview.model_dump(mode="json") if site.multiview else None,
            "recommended": rec.model_dump(mode="json"),
            "readback": readback.model_dump(mode="json") if readback else None,
            "findings": [asdict(f) for f in findings],
            "suggestions": [asdict(f) for f in suggestions],
            "ok": not any(f.level == "error" for f in findings),
            "in_app": self.multiview_in_app,
        }

    # -- rutekart from the picture (setup step 6, VI-5) -----------------------------------

    def _load_multiview(self) -> None:
        saved = self.deps.store.get_kv(MV_KEY) if self.deps.store is not None else None
        if not isinstance(saved, dict):
            return
        try:
            self._use_multiview(MultiviewMap.model_validate(saved))
        except ValidationError as exc:
            log.warning("rutekartet i databasen kan ikke brukes, bruker filen: %s", exc)

    def _use_multiview(self, m: MultiviewMap | None) -> None:
        self.multiview_in_app = m is not None
        self.deps.site = self.deps.site.model_copy(
            update={"multiview": m if m is not None else self._file_multiview}
        )
        if self.on_vision_map is not None and self.deps.site.multiview is not None:
            self.on_vision_map(self.deps.site.multiview)

    def _mv_picture(self) -> Any | None:
        """The newest whole multiview from the video layer (BGR array), or ``None``."""
        self.vision_thumb("MV")  # also asks the video layer to keep sending
        data = self.runtime.vision_thumbs.get("MV")
        ms = self.runtime.vision_thumbs_ms
        if data is None or ms is None or self.now - ms > 3_000:
            return None
        try:
            import cv2
            import numpy as np
        except ImportError:
            return None
        buf = np.frombuffer(base64.b64decode(data), dtype=np.uint8)
        return cv2.imdecode(buf, cv2.IMREAD_COLOR)

    def multiview_suggest(self) -> dict[str, Any]:
        """«Foreslå fra bildet»: windows found in the picture, sources from the ATEM. Nothing
        is saved; the technician adjusts the corners and saves."""
        from cutcut.vision.grid import find_grid, program_side

        site = self.deps.site
        frame = self._mv_picture()
        grid = find_grid(frame) if frame is not None else None
        notes: list[str] = []
        if frame is not None and grid is not None and grid.found:
            big, small = grid.big, grid.small
            notes.append("Rutene er funnet i bildet fra multiviewen.")
            side = program_side(frame, grid)
        else:
            base = site.multiview or mv.recommended(mv.StudioInputs.from_site(site))
            pvw = next(t for t in base.tiles if t.source == "preview").rect
            pgm = next(t for t in base.tiles if t.source == "program").rect
            big = (pvw, pgm) if base.preview_left else (pgm, pvw)
            small = tuple(t.rect for t in base.small_windows())
            side = None
            notes.append(
                "Fant ikke rutene i bildet"
                + (" (ikke noe bilde fra videolaget nå)" if frame is None else "")
                + ": rutene er plassert som i dag. Dra hjørnene på plass."
            )
        suggestion, more = mv.suggest_map(
            big,
            small,
            mv.StudioInputs.from_site(site),
            readback=self._mv_readback(),
            current=site.multiview,
            program_side=side,
            switcher=self.devices.atem.model,
        )
        return {
            "map": suggestion.model_dump(mode="json"),
            "found": bool(grid is not None and grid.found),
            "notes": notes + more,
        }

    def check_multiview_map(self, data: dict[str, Any]) -> MultiviewMap:
        try:
            m = MultiviewMap.model_validate(data)
        except ValidationError as exc:
            first = exc.errors()[0]
            msg = str(first["msg"]).removeprefix("Value error, ")
            raise CommandError(f"Rutekartet kan ikke brukes: {msg}") from exc
        errors = [f for f in mv.check_map(m, mv.StudioInputs.from_site(self.deps.site))]
        bad = [f for f in errors if f.level == "error"]
        if bad:
            raise CommandError(f"Rutekartet kan ikke brukes: {bad[0].message}")
        return m

    def save_multiview_map(self, data: dict[str, Any], role: Role, actor: str) -> dict[str, Any]:
        """«Lagre rutekart»: kept in the app and sent to the video layer at once. Not during a
        recording: the video layer would read other windows in the middle of it."""
        if self.sessions.recording:
            raise CommandError("Rutekartet kan ikke endres mens opptak pågår.")
        m = self.check_multiview_map(data)
        m = m.model_copy(update={"status": "approved", "source": f"Setup-hjelperen, {actor}"})
        if self.deps.store is not None:
            self.deps.store.put_kv(MV_KEY, m.model_dump(mode="json"), self.deps.clock.now())
        self._use_multiview(m)
        self._audit(role, actor, "multiview_map", layout=m.layout)
        self._check_multiview()
        self._autosave()
        return self.multiview_status()

    def reset_multiview_map(self, role: Role, actor: str) -> dict[str, Any]:
        """Back to ``equipment/multiview_map.yaml``."""
        if self.sessions.recording:
            raise CommandError("Rutekartet kan ikke endres mens opptak pågår.")
        if self.deps.store is not None:
            self.deps.store.put_kv(MV_KEY, None, self.deps.clock.now())
        self._use_multiview(None)
        self._audit(role, actor, "multiview_map_reset")
        self._check_multiview()
        self._autosave()
        return self.multiview_status()

    def check_multiview_now(self, role: Role, actor: str) -> dict[str, Any]:
        """«Sjekk nå» on the setup screen, e.g. after someone changed the ATEM."""
        self._check_multiview()
        self._audit(role, actor, "multiview_check")
        return self.multiview_status()

    def _check_multiview(self) -> None:
        """Warn the technician when the multiview does not match the rutekart (CutCut would
        read the wrong camera); say so when a later check finds it fixed."""
        try:
            status = self.multiview_status()
        except Exception:  # never let a check stop the studio
            log.exception("multiview-sjekk feilet")
            return
        errors = [f for f in status["findings"] if f["level"] == "error"]
        key = "|".join(f"{f['check']}:{f['where']}" for f in errors)
        if key == self._mv_errors:
            return
        self._mv_errors = key
        self._mv_first_error = errors[0]["message"] if errors else None
        if errors:
            more = f" (+{len(errors) - 1} til)" if len(errors) > 1 else ""
            self._alert("warn", "H-MV", f"Multiview: {errors[0]['message']}{more}")
        elif self._mv_seen_error:
            self._alert("info", "H-MV", "Multiview stemmer med rutekartet igjen.")
        self._mv_seen_error = self._mv_seen_error or bool(errors)

    def _track_session(self) -> None:
        """Keep the session history (spec 8.4 «Opptak i dag»): saved on every step change, so
        a restart loses nothing that was finished."""
        session = self.sessions.session
        key = (session.session_id, session.touch_step) if session else None
        if key == self._tracked:
            return
        wall = self.deps.clock.now()
        if self._tracked is not None and (key is None or key[0] != self._tracked[0]):
            self._end_tracked(self._tracked[0], wall)
        self._tracked = key
        if session is None:
            return
        record = self.history.get(session.session_id)
        if record is None:
            record = SessionRecord(session=session.model_copy(deep=True), started_at=wall)
            self.history[session.session_id] = record
            while len(self.history) > HISTORY_KEEP:
                self.history.pop(next(iter(self.history)))
        record.session = session.model_copy(deep=True)
        if session.touch_step is TouchStep.DONE and record.ended_at is None:
            record.ended_at = wall
        self._save_record(record)

    def _end_tracked(self, session_id: str, wall: datetime) -> None:
        record = self.history.get(session_id)
        if record is not None and record.ended_at is None:
            record.ended_at = wall
            self._save_record(record)

    def _save_record(self, record: SessionRecord) -> None:
        if self.deps.store is not None:
            self.deps.store.upsert_session(record.session, record.started_at, record.ended_at)

    def session_history(self, since: datetime) -> list[dict[str, Any]]:
        """Newest first, from the database when there is one (survives restarts)."""
        if self.deps.store is not None:
            self.deps.store.flush()
            rows = self.deps.store.sessions_since(since)
        else:
            rows = [
                {
                    "session": r.session.model_dump(mode="json"),
                    "started_at": r.started_at.isoformat(),
                    "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                }
                for r in reversed(self.history.values())
                if r.started_at >= since
            ]
        return [_history_row(r) for r in rows]

    def _on_step(self, result: StepResult) -> None:
        return None

    def _on_decision(self, d: Decision) -> None:
        item = d.model_dump(mode="json")
        self.decisions.append(item)
        self.hub.publish("decision", item)

    def apply(self, actions: list[Action]) -> None:
        now = self.now
        for action in actions:
            match action:
                case PearlStart():
                    if not self.deps.recorder.start(now):
                        self._alert("error", "H-PRL-1", "Pearl svarer ikke", for_user=True)
                    elif self.iso_wanted():
                        self._iso_with_pearl()
                case PearlStop():
                    self.deps.recorder.stop(now)
                    if self._iso_running():  # I7: only a person stops it; ask
                        self._alert(
                            "warn",
                            "ISO",
                            "Pearl-opptaket er stoppet, men ISO-opptaket i ATEM går fortsatt. "
                            "Stopp det under Opptak når det er ferdig.",
                        )
                case EngineCommand(command=cmd):
                    self.runtime.command(cmd)
                case Alert(level=level, code=code, message_nb=msg, for_user=for_user):
                    self._alert(level, code, msg, for_user=for_user)
                case Notice(message_nb=msg, ms=ms):
                    self.notice, self.notice_until = msg, now + ms
                    self.hub.publish("touch", {"notice": msg})

    def _alert(
        self,
        level: Literal["info", "warn", "error"],
        code: str,
        msg: str,
        for_user: bool = False,
        log_it: bool = True,
    ) -> None:
        self._alert_seq += 1
        rec = AlertRecord(self._alert_seq, level, code, msg, self.deps.clock.now(), for_user)
        self.alerts.append(rec)
        del self.alerts[:-50]
        if log_it:  # health checks log their own start and end
            log.log(logging.ERROR if level == "error" else logging.INFO, msg, extra={"check": code})
            if level == "error" and self.notifier is not None:
                self.notifier.on_alert(code, msg)  # a recording failed: email at once (HS-3)
        self.hub.publish("alert", self._alert_info(rec).model_dump(mode="json"))

    @staticmethod
    def _alert_info(a: AlertRecord) -> AlertInfo:
        return AlertInfo(
            id=a.id,
            level=a.level,
            code=a.code,
            message=a.message,
            ts=a.ts.isoformat(),
            for_user=a.for_user,
            acknowledged=a.acknowledged,
        )

    # -- state for the screens ------------------------------------------------------------

    def meters(self) -> dict[str, Meter]:
        frames = self.runtime.latest_mics
        sp = self.engine.speakers
        out: dict[str, Meter] = {}
        for p in self.show.participants:
            f = frames.get(p.mic)
            t = sp.get(p.id)
            out[p.mic.value] = Meter(
                level_db=round(f.level_db, 1) if f else -90.0,
                vad=round(f.vad, 2) if f else 0.0,
                speaking=t.speaking,
                muted=t.muted,
            )
        laptop = frames.get(MicId.M5)
        out["M5"] = Meter(
            level_db=round(laptop.level_db, 1) if laptop else -90.0,
            vad=round(laptop.vad, 2) if laptop else 0.0,
            speaking=bool(laptop and laptop.vad >= self.engine.rules.T1_vad_threshold),
        )
        return out

    def state(self) -> StudioState:
        e, s, now = self.engine, self.sessions, self.now
        session = s.session
        return StudioState(
            studio=StudioInfo(
                name=self.devices.studio,
                simulator=self.deps.simulator,
                version=__version__,
                show_types={k: v.name for k, v in self.deps.show_types.types.items()},
                show_type=self.show_type,
                show_id=self.show.id,
                inputs=self._inputs(),
                support_email=self.devices.support.email or None,
            ),
            session=session.model_copy(deep=True) if session else None,
            touch=TouchInfo(
                step=s.step.value,
                countdown_ms=s.countdown_left_ms(now),
                notice=self.notice,
                help=s.help_requested,
                default_show=s.default_show,
                done_logout_ms=max(0, DONE_LOGOUT_MS - (now - s.step_since))
                if s.step is TouchStep.DONE
                else 0,
                login=self.login_mode,
                audio_check=self.audio_check_info(),
            ),
            engine=EngineInfo(
                mode=e.mode.value,
                program=e.program,
                preview=e.preview,
                pv_state=e.pv_state.value,
                auto=e.auto,
                lock=e.lock,
                shadow=e.shadow,
                paused=e.paused,
                content_enabled=e.content_enabled,
                content_active=e.content.active,
                audio_ok=not e.s4_paused,
                program_ms=max(0, now - e.program_since),
            ),
            participants=[
                ParticipantInfo(
                    id=p.id.value,
                    name=p.name,
                    role=p.role,
                    mic=p.mic.value,
                    camera=p.camera.value,
                    color=PARTICIPANT_COLORS[p.id.value],
                )
                for p in self.show.participants
            ],
            recording=self._recording_info(),
            rules=RulesInfo(
                preset=self.preset,
                features={
                    k: v for k, v in self.features.model_dump().items() if isinstance(v, bool)
                },
                overrides=dict(self.overrides),
                switches=self.switches_info(),
            ),
            alerts=[self._alert_info(a) for a in self.alerts if not a.acknowledged][-20:],
            runtime=RuntimeInfo(
                ticks=self.runtime.stats.ticks,
                max_step_ms=round(self.runtime.stats.max_step_ms, 2),
                skipped_ticks=self.runtime.stats.skipped_ticks,
                processes=self.processes_info(),
                vision=self.vision_live(),
            ),
            health=self.health_info(),
        )

    def _publish_state(self) -> None:
        state = self.state().model_dump(mode="json")
        changed = {k: v for k, v in state.items() if self._last_state.get(k) != v}
        if changed:
            self._last_state = state
            self.hub.publish("state", changed)

    # -- commands (10.1). Every change that affects the broadcast is audited. -------------

    def _audit(self, role: Role, actor: str, action: str, **detail: Any) -> None:
        if self.deps.store is not None:
            self.deps.store.audit(self.deps.clock.now(), role, actor, action, **detail)

    def _guard(self, fn: Any, *args: Any) -> list[Action]:
        try:
            result: list[Action] = fn(*args)
        except SessionError as exc:
            raise CommandError(str(exc)) from exc
        return result

    def login(self, user: User, role: Role, actor: str, source: str = "card") -> None:
        had = self.sessions.session
        self.apply(self._guard(self.sessions.login, user, self.now, self.deps.clock.now(), source))
        if self.sessions.session is not had:
            self._start_with_type_preset()
        self._audit(role, actor, "session_start", username=user.username)

    def logout(self, role: Role, actor: str) -> None:
        self.apply(self._guard(self.sessions.logout, self.now))
        self._audit(role, actor, "session_end")

    def set_show(self, choice: ShowChoice, role: Role, actor: str) -> None:
        update: dict[str, Any] = {"type": self.show_type}  # the studio decides (D-036)
        if self._type().audio_only:
            update["video"] = False
        choice = choice.model_copy(update=update)
        show = self._show_for(choice.participants)
        self.apply(self._guard(self.sessions.set_show, choice, self.now))
        if show.id != self.show.id:
            self.show = show
            self._rebuild_engine()
        self._audit(role, actor, "set_show", **choice.model_dump())

    def start_recording(self, by: StartedBy, role: Role, actor: str) -> None:
        self.apply(self._guard(self.sessions.start, self.now, by))
        self._audit(role, actor, "recording_start", by=by)

    def stop_recording(self, by: StartedBy, role: Role, actor: str) -> None:
        self.apply(self._guard(self.sessions.stop, self.now, by))
        self._audit(role, actor, "recording_stop", by=by)

    def touch_step(self, step: TouchStep, role: Role, actor: str) -> None:
        self.apply(self._guard(self.sessions.move_to, step, self.now))
        self._audit(role, actor, "touch_step", step=step.value)

    def again(self, role: Role, actor: str) -> None:
        self.apply(self._guard(self.sessions.again, self.now, self.deps.clock.now()))
        self._audit(role, actor, "session_again")

    def touched(self) -> None:
        self.sessions.touched(self.now)

    def touch_heartbeat(self) -> None:
        """The touch screen says it is alive (every 5 s). The kiosk guard reloads Edge when it
        stops (SO-6); ``H-PROC-touch`` is added the first time a touch screen reports."""
        first = self._touch_seen is None
        self._touch_seen = self.now
        if first:
            self.health.add(
                health_checks.touch_screen(self.touch_heartbeat_age, self.deps.clock.now)
            )

    def _maybe_add_video_check(self) -> None:
        """``H-VID-1`` and ``H-VID-3`` from the first time the video layer reports (M3)."""
        rt = self.runtime
        if rt.vision_status_ms is None:
            return
        seen, says = self._pgm_seen(), self._pgm_atem()
        if seen is not None and says is not None and seen != says:
            if self._pgm_apart_since is None:
                self._pgm_apart_since = self.now
        else:
            self._pgm_apart_since = None
        if self._video_check:
            return
        self._video_check = True
        self.health.add(
            health_checks.video(
                lambda: None if rt.vision_frame_ms is None else self.now - rt.vision_frame_ms,
                lambda: rt.vision_status,
                self.deps.clock.now,
            )
        )
        video = self.deps.site.baseline.video
        self.health.add(
            health_checks.video_format(
                lambda: rt.vision_status,
                video.width if video else 1920,
                video.height if video else 1080,
                self.deps.clock.now,
            )
        )
        self.health.add(
            health_checks.program_confirm(
                self._pgm_seen,
                self._pgm_atem,
                lambda: 0 if self._pgm_apart_since is None else self.now - self._pgm_apart_since,
                self.deps.clock.now,
            )
        )

    def vision_live(self) -> bool:
        """The video layer delivers pictures (the screens show cut-outs instead of drawings)."""
        ms = self.runtime.vision_frame_ms
        return ms is not None and self.now - ms <= 2_000

    def vision_thumb(self, source: str) -> bytes | None:
        """The newest cut-out of ``source`` (C1…, LAPTOP, PVW, PGM), and ask the video layer to
        keep sending them for a while (D-056: only while someone looks)."""
        if self.on_vision_want is not None and self.now - self._want_sent >= 2_000:
            self._want_sent = self.now
            self.on_vision_want()
        ms = self.runtime.vision_thumbs_ms
        data = self.runtime.vision_thumbs.get(source)
        if data is None or ms is None or self.now - ms > 3_000:
            return None
        return base64.b64decode(data)

    def _pgm_seen(self) -> str | None:
        src = self.runtime.vision_pgm.get("source")
        return str(src) if src else None

    def _pgm_atem(self) -> str | None:
        rb = self.runtime.atem
        if rb is None or rb.program_layout is not None or rb.program.value == "SUPERSOURCE":
            return None
        return rb.program.value

    def touch_heartbeat_age(self) -> int | None:
        return None if self._touch_seen is None else self.now - self._touch_seen

    def help(self, role: Role, actor: str) -> None:
        self.apply(self.sessions.help(self.now))
        self._audit(role, actor, "help")

    def acknowledge(self, alert_id: int, role: Role, actor: str) -> None:
        for a in self.alerts:
            if a.id == alert_id:
                a.acknowledged = True
        if all(a.acknowledged for a in self.alerts if a.code == "HELP"):
            self.sessions.help_requested = False
        self._audit(role, actor, "acknowledge", alert=alert_id)

    def set_auto(self, on: bool, role: Role, actor: str) -> None:
        self.runtime.command(SetAuto(on=on))
        self._audit(role, actor, "auto", on=on)

    def set_lock(self, on: bool, role: Role, actor: str) -> None:
        self.runtime.command(SetLock(on=on))
        self._audit(role, actor, "lock", on=on)

    def set_shadow(self, on: bool, role: Role, actor: str) -> None:
        self.runtime.command(SetShadow(on=on))
        self._audit(role, actor, "shadow", on=on)

    def cut(self, shot: str, role: Role, actor: str) -> None:
        self._check_shot(shot)
        self.runtime.command(ManualCut(shot))
        self._audit(role, actor, "cut", shot=shot)

    def preview(self, shot: str, role: Role, actor: str) -> None:
        self._check_shot(shot)
        self.runtime.command(ManualPreview(shot))
        self._audit(role, actor, "preview", shot=shot)

    def set_content(self, enabled: bool, role: Role, actor: str) -> None:
        self.runtime.command(SetContentEnabled(enabled=enabled))
        self._audit(role, actor, "content", enabled=enabled)

    # -- framing and slow zoom on the PTZ cameras (F1, Z1, Z2) -------------------------------

    def _slow_zoom_allowed(self, cam: CameraId) -> bool:
        """The camera guard lets a slow zoom step through on air only when the switch is on
        and the show allows slow zoom on that camera (Z3)."""
        cfg = self.show.cameras.get(cam)
        return self.features.mode("slow_zoom") == "on" and cfg is not None and cfg.slow_zoom

    # -- the cameras from the technician window (Kameraer, AT1–AT6) ---------------------------

    def _cams(self) -> CameraService:
        if self.deps.cameras is None:
            raise CommandError("Kameraene styres ikke fra denne PC-en.")
        return self.deps.cameras

    def _verdict(self, verdict: str | None) -> None:
        if verdict is None:
            raise CommandError("CutCut styrer ikke dette kameraet.")
        if verdict != "queued":
            raise CommandError(VERDICT_TEXT.get(verdict, verdict))

    def cameras_info(self) -> list[dict[str, Any]]:
        cams = self.deps.cameras
        if cams is None:
            return []
        out = []
        for cam, g in sorted(cams.guards.items()):
            cfg = self.show.cameras.get(cam)
            pos = g.st.position
            out.append(
                {
                    "id": cam.value,
                    "model": cams.models.get(cam),
                    "online": g.st.ok,
                    "tracking": g.st.tracking,
                    "can_track": cfg is not None and cfg.driver == "obsbot" and cfg.role != "bird",
                    "presets": dict(cfg.presets) if cfg else {},
                    "position": None
                    if pos is None
                    else {
                        "pan": round(pos.pan, 1),
                        "tilt": round(pos.tilt, 1),
                        "zoom": round(pos.zoom, 3),
                    },
                    "last_refused": g.st.last_refused,
                    "last_error": g.st.last_error,
                }
            )
        return out

    def camera_preset(self, cam: CameraId, n: int, store: bool, role: Role, actor: str) -> None:
        """Recall (or, admin, save) a preset. Saving does not move the camera."""
        cmd: CameraCommand = StorePreset(n) if store else RecallPreset(n, speed=0.3)
        self._verdict(self._cams().submit(cam, cmd))
        self._audit(role, actor, "camera_preset", camera=cam.value, n=n, store=store)

    def camera_nudge(
        self, cam: CameraId, pan: float, tilt: float, zoom: float, role: Role, actor: str
    ) -> None:
        self._verdict(self._cams().submit(cam, Nudge(pan=pan, tilt=tilt, zoom=zoom)))
        self._audit(role, actor, "camera_nudge", camera=cam.value)

    def set_tracking(self, cam: CameraId, on: bool, role: Role, actor: str) -> None:
        """AT1: AI-tracking on or off for one camera. Needs the switch; in shadow it is only
        logged. Off is always allowed (AT5: the camera stays where it is)."""
        mode = self.features.mode("ai_tracking")
        cfg = self.show.cameras.get(cam)
        if on and (cfg is None or cfg.driver != "obsbot" or cfg.role == "bird"):
            raise CommandError("AI-tracking finnes bare på OBSBOT, og aldri på fugleperspektivet.")
        if on and mode == "off":
            raise CommandError("Slå på AI-tracking under Regi → Brytere først.")
        if on and mode == "shadow":
            self._alert(
                "info",
                RuleId.AT1.value,
                f"Skygge: AI-tracking ville blitt slått på for {cam.value}.",
            )
            self._audit(role, actor, "tracking_shadow", camera=cam.value)
            return
        cams = self._cams()
        self._verdict(cams.set_tracking(cam, on))  # on: calm settings first (AT2)
        rule = RuleId.AT2 if on else RuleId.AT5
        self._audit(role, actor, "tracking", camera=cam.value, on=on, rule=rule.value)

    def _tracking_off_after_session(self) -> None:
        """AT6: tracking is always off when a session ends."""
        had, self._had_session = self._had_session, self.sessions.session is not None
        cams = self.deps.cameras
        if cams is None:
            return
        self.runtime.feed_cameras_tracking(cams.tracking())
        if had and not self._had_session:
            for cam in cams.tracking():
                cams.set_tracking(cam, False)
                log.info("%s: AI-tracking av etter økten (%s)", cam.value, RuleId.AT6.value)

    def _camera_intent(self, intent: Intent) -> None:
        cams = self.deps.cameras
        if cams is None:
            return
        match intent:
            case FrameCamera(camera=cam, framing=framing):
                cfg = self.show.cameras.get(cam)
                preset = cfg.presets.get(framing) if cfg is not None else None
                if preset is not None:
                    verdict = cams.frame(cam, preset)
                    if verdict not in (None, "queued"):
                        log.info("%s: utsnitt %s ikke sendt (%s)", cam.value, framing, verdict)
            case SlowZoom(camera=cam, amount=amount, duration_ms=ms):
                cams.slow_zoom(cam, amount, ms / 1000)
            case StopZoom(camera=cam):
                cams.stop_zoom(cam)
            case NudgeCamera(camera=cam, pan=pan, tilt=tilt):
                cams.submit(cam, Nudge(pan=pan, tilt=tilt))

    # -- switches: off, shadow, on (spec 5.13, F-1) -------------------------------------------

    def _switch_prereq(self, name: str) -> tuple[bool, bool, str | None]:
        """(can shadow, can switch on, why not). Shadow sends nothing, so it only needs the
        rules and their measurements; «on» also needs the equipment to act."""
        if name not in IMPLEMENTED_SWITCHES:
            return False, False, "Reglene bygges før studioperioden (docs/plans/for-studio.md)."
        if name in ("video_confirm", "reactions") and not self.runtime.vision_status.get("faces"):
            why = "Krever den tunge delen av videolaget (ansikt og munn på GPU)."
            return False, False, why
        steered = set(self.deps.cameras.guards) if self.deps.cameras is not None else set()
        if name == "framing_variety":
            ok = [
                c
                for c, cfg in self.show.cameras.items()
                if c in steered and cfg.role == "closeup" and {"tight", "wide"} <= set(cfg.presets)
            ]
            if not ok:
                why = "Ingen nærbildekameraer med presetene «tight» og «wide» styres av CutCut."
                return True, False, why
        if name == "ai_tracking":
            ok = [
                c
                for c, cfg in self.show.cameras.items()
                if c in steered and cfg.driver == "obsbot" and cfg.role != "bird"
            ]
            if not ok:
                return True, False, "Ingen OBSBOT-kameraer styres av CutCut."
        if name == "slow_zoom":
            ok = [c for c, cfg in self.show.cameras.items() if c in steered and cfg.slow_zoom]
            if not ok:
                why = (
                    "Ingen kameraer har langsom zoom slått på i showet "
                    f"({RuleId.Z3.value}, prøves per kamera)."
                )
                return True, False, why
        if name == "layouts":
            found = self._atem_macros()
            problems = macro_check(found) if found is not None else ["ATEM kan ikke leses"]
            if problems:  # DA-7: the engine would take a SuperSource that shows something else
                return True, False, f"{problems[0]}. Lag makroene i ATEM (7.2)."
        return True, True, None

    def switches_info(self) -> list[SwitchInfo]:
        out = []
        for name in SWITCHES:
            can_shadow, can_on, why = self._switch_prereq(name)
            out.append(
                SwitchInfo(
                    key=name,
                    mode=self.features.mode(name),
                    can_shadow=can_shadow,
                    can_on=can_on,
                    why=why,
                )
            )
        return out

    def set_features(self, changes: dict[str, bool | FeatureMode], role: Role, actor: str) -> None:
        """``true``/``"on"``, ``false``/``"off"`` or ``"shadow"`` per switch. Base mode
        switches (bird, content) are only on or off."""
        known = set(type(self.features).model_fields) - {"shadow"}
        unknown = set(changes) - known
        if unknown:
            raise CommandError(f"Ukjent bryter: {', '.join(sorted(unknown))}")
        features = self.features
        for name, value in changes.items():
            mode: FeatureMode = ("on" if value else "off") if isinstance(value, bool) else value
            if mode not in ("off", "shadow", "on"):
                raise CommandError(f"Ugyldig verdi for {name}: {value}")
            if name not in SWITCHES:
                if mode == "shadow":
                    raise CommandError(f"{name} er en del av grunnmodus og har ikke skygge.")
                features = features.model_copy(update={name: mode == "on"})
                continue
            if mode != "off" and mode != features.mode(name):
                can_shadow, can_on, why = self._switch_prereq(name)
                if (mode == "on" and not can_on) or (mode == "shadow" and not can_shadow):
                    raise CommandError(f"Bryteren kan ikke slås på: {why}")
            features = features.with_mode(name, mode)
        self.features = features
        self._reconfigure()
        self._audit(role, actor, "features", **{k: str(v) for k, v in changes.items()})

    def _switches_failed(self) -> None:
        """A switch whose rules raised goes to shadow and the technician is told (F-1)."""
        failed = self.engine.failed_switches - self._failed_seen
        if not failed:
            return
        self._failed_seen |= failed
        for name in sorted(failed):
            if self.features.mode(name) == "on":
                self.features = self.features.with_mode(name, "shadow")
            self._alert(
                "warn",
                "F-1",
                f"Bryteren {name} feilet og går nå i skygge. Grunnmodus klipper som før.",
            )
        self._reconfigure()

    def set_preset(self, preset: RulesPreset, role: Role, actor: str) -> None:
        self.preset = preset
        self._reconfigure()
        self._audit(role, actor, "preset", preset=preset)

    def set_overrides(self, changes: dict[str, float | None], role: Role, actor: str) -> None:
        """Fine tuning of single rule values on top of the preset (ADR-0011). ``None`` resets
        a value to the preset. Out-of-range values are refused and nothing changes."""
        updated = dict(self.overrides)
        for name, value in changes.items():
            if value is None:
                updated.pop(name, None)
            else:
                updated[name] = value
        try:
            self.deps.presets.get(self.preset).with_overrides(
                {**self.show.rules_override, **updated}
            )
        except ValueError as exc:
            raise CommandError(f"Ugyldig regelverdi: {_why(exc)}") from exc
        self.overrides = updated
        self._reconfigure()
        self._audit(role, actor, "rules_override", **{k: v for k, v in changes.items()})

    def _reconfigure(self) -> None:
        """ADR-0011: switches and presets change live, from the next tick."""
        merged = self._merged(self.show)
        rules = effective_rules(merged, self.deps.presets)
        self.engine.set_config(EngineConfig.from_show(merged, rules))
        self._save_tuning()

    def _check_shot(self, shot: str) -> None:
        if not is_shot(shot):
            raise CommandError(f"Ukjent bilde: {shot}")
        if shot.startswith("CU:") and shot[3:] not in {p.id.value for p in self.show.participants}:
            raise CommandError(f"{shot[3:]} er ikke med i dette oppsettet.")

    def rules_info(self) -> dict[str, Any]:
        """Everything the tuning screen needs: current and preset values, overrides, limits."""
        props = RuleParams.model_json_schema()["properties"]
        limits = {
            name: {
                "type": p.get("type"),
                "min": p.get("minimum", p.get("exclusiveMinimum")),
                "max": p.get("maximum", p.get("exclusiveMaximum")),
            }
            for name, p in props.items()
        }
        return {
            "preset": self.preset,
            "values": self.engine.rules.model_dump(),
            "preset_values": self.deps.presets.get(self.preset).model_dump(),
            "overrides": dict(self.overrides),
            "limits": limits,
            "ids": [r.value for r in RuleId],
        }
