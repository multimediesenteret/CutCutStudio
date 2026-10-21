"""The studio as one service: engine, session, recorder, alerts and live data for the screens.

All state lives here, not in the screens (12.5): the API reads it and sends commands to it,
and the screens get a full snapshot on connect and changes afterwards. The same class runs in
the studio (real devices) and in ``cutcut sim`` (fake devices and synthetic talkers).
"""

from __future__ import annotations

import asyncio
import base64
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, tzinfo
from pathlib import Path
from typing import Any, Final, Literal, Protocol

from pydantic import ValidationError

from cutcut import __version__
from cutcut.app import devices
from cutcut.app.hub import Hub
from cutcut.app.state import (
    AlertInfo,
    EngineInfo,
    HealthInfo,
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
    TouchInfo,
)
from cutcut.common.clock import Clock
from cutcut.common.config import (
    ConfigError,
    RuleParams,
    RulePresets,
    ShowTypes,
    Site,
    effective_rules,
)
from cutcut.common.ids import MicId, RuleId, is_shot
from cutcut.common.models.decision import Decision
from cutcut.common.models.multiview import MultiviewReadback
from cutcut.common.models.session import (
    GUEST_USER,
    RecordingStatus,
    Session,
    ShowChoice,
    StartedBy,
    TouchStep,
    User,
)
from cutcut.common.models.show import Features, RulesPreset, ShowConfig
from cutcut.common.models.site import Devices
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
from cutcut.core.runtime import CoreRuntime, Executor
from cutcut.devices.atem.macros import check as macro_check
from cutcut.health import HealthCheck, HealthEngine, HealthEvent
from cutcut.health import checks as health_checks
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

log = logging.getLogger(__name__)

STATE_EVERY_MS: Final = 100  # 10 Hz (docs/design/gui-konsept.md)
METERS_EVERY_MS: Final = 50  # 20 Hz (spec 10.2)
LOG_KEEP: Final = 200
TUNING_KEY: Final = "studio.tuning"
LOGIN_KEY: Final = "studio.login"
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
        self.alerts: list[AlertRecord] = []
        clock = self.deps.clock
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

    def _load_login_mode(self) -> None:
        if self.deps.store is None:
            return
        saved = self.deps.store.get_kv(LOGIN_KEY)
        if saved in ("open", "card"):
            self.login_mode = saved

    def set_login_mode(self, mode: LoginMode, role: Role, actor: str) -> None:
        """«Innlogging» in the technician's settings (D-057). Card login needs the card reader
        and the NTNU API; until they are set up, users start with the button on the screen."""
        if mode not in ("open", "card"):
            raise CommandError("Ukjent innlogging.")
        self.login_mode = mode
        if self.deps.store is not None:
            self.deps.store.put_kv(LOGIN_KEY, mode, self.deps.clock.now())
        self._audit(role, actor, "login_mode", mode=mode)

    def start_without_card(self, role: Role, actor: str) -> None:
        """«Start uten kort» on the touch screen: a session for «Gjest» (no Panopto owner)."""
        if self.login_mode != "open":
            raise CommandError("Bruk NTNU-kortet ditt, eller trykk Hjelp.")
        self.login(GUEST_USER, role, actor, source="guest")

    def _load_tuning(self) -> None:
        """Preset, switches and fine tuning survive a restart (the studio runs unattended)."""
        if self.deps.store is None:
            return
        saved = self.deps.store.get_kv(TUNING_KEY)
        if not isinstance(saved, dict):
            return
        try:
            preset = saved.get("preset", self.preset)
            features = self.features.model_copy(update=saved.get("features", {}))
            overrides = {str(k): v for k, v in saved.get("overrides", {}).items()}
            effective_rules(
                self._merged_with(self.show, preset, features, overrides), self.deps.presets
            )
        except (ValueError, ConfigError) as exc:
            log.warning("Lagret tuning ble ikke brukt: %s", exc)
            return
        self.preset, self.features, self.overrides = preset, features, overrides

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
        try:
            effective = devices.apply(self.deps.site.devices, updated)
        except devices.DeviceSettingsError as exc:
            raise CommandError(str(exc)) from exc
        self.device_overrides, self.devices = updated, effective
        if self.on_devices is not None:
            self.on_devices(effective)  # e.g. point the Companion and Pearl clients elsewhere
        if self.deps.store is not None:
            self.deps.store.put_kv(devices.DEVICES_KEY, updated, self.deps.clock.now())
        self._reconfigure()
        self._audit(role, actor, "devices", **{k: v for k, v in changes.items()})

    def devices_info(self) -> dict[str, Any]:
        return {
            "studio": self.devices.studio,
            "atem_model": self.devices.atem.model,
            "rows": devices.rows(self.deps.site.devices, self.devices, self.device_overrides),
        }

    def _recording_info(self) -> RecordingInfo:
        session = self.sessions.session
        info = RecordingInfo(
            pearl=self.deps.recorder.state.value,
            duration_s=session.recording.duration_s if session else 0,
            started_by=session.recording.started_by if session else None,
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
        if not self.deps.simulator:  # the simulator runs on files in the repo: never write
            write_baseline(site.root / "baseline.yaml", new)
        self.deps.site = site.model_copy(update={"baseline": new})
        if self.on_audio_config is not None:
            leak = {
                s.value: {d.value: v for d, v in row.items()}
                for s, row in new.audio.leak_db.items()
            }
            self.on_audio_config({"leak_db": leak})
        self._audit(role, actor, "mic_check_save", mics=sorted(r.value for r in check.results))
        self._alert("info", "SETUP-5", f"Mikrofonene er målt og lagret som fasit av {actor}.")
        return self.mic_check_status()

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
            for a in self.alerts:
                if a.code == r.id:
                    a.acknowledged = True
            return
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
        return checks

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
                await self._maybe_morning_check()
            except Exception:  # health must never take core down
                log.exception("helsesjekkene feilet")
            await asyncio.sleep(every_s)

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
        }

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
                case PearlStop():
                    self.deps.recorder.stop(now)
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
                show_id=self.show.id,
                inputs=self._inputs(),
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
                features=self.features.model_dump(),
                overrides=dict(self.overrides),
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
        self.apply(self._guard(self.sessions.login, user, self.now, self.deps.clock.now(), source))
        self._audit(role, actor, "session_start", username=user.username)

    def logout(self, role: Role, actor: str) -> None:
        self.apply(self._guard(self.sessions.logout, self.now))
        self._audit(role, actor, "session_end")

    def set_show(self, choice: ShowChoice, role: Role, actor: str) -> None:
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

    def set_features(self, changes: dict[str, bool], role: Role, actor: str) -> None:
        unknown = set(changes) - set(type(self.features).model_fields)
        if unknown:
            raise CommandError(f"Ukjent bryter: {', '.join(sorted(unknown))}")
        if changes.get("layouts") and not self.features.layouts:
            found = self._atem_macros()
            problems = macro_check(found) if found is not None else []
            if problems:  # DA-7: the engine would take a SuperSource that shows something else
                raise CommandError(
                    f"Layoutene kan ikke slås på: {problems[0]}. Lag makroene i ATEM (7.2)."
                )
        self.features = self.features.model_copy(update=changes)
        self._reconfigure()
        self._audit(role, actor, "features", **changes)

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
