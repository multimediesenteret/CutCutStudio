"""The studio as one service: engine, session, recorder, alerts and live data for the screens.

All state lives here, not in the screens (12.5): the API reads it and sends commands to it,
and the screens get a full snapshot on connect and changes afterwards. The same class runs in
the studio (real devices) and in ``cutcut sim`` (fake devices and synthetic talkers).
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal, Protocol

from pydantic import ValidationError

from cutcut import __version__
from cutcut.app import devices
from cutcut.app.hub import Hub
from cutcut.app.state import (
    AlertInfo,
    EngineInfo,
    Meter,
    ParticipantInfo,
    RecordingInfo,
    RulesInfo,
    RuntimeInfo,
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
    RecordingStatus,
    Session,
    ShowChoice,
    StartedBy,
    TouchStep,
    User,
)
from cutcut.common.models.show import Features, RulesPreset, ShowConfig
from cutcut.common.models.site import Devices
from cutcut.common.store import Store
from cutcut.core.engine import Engine, StepResult
from cutcut.core.inputs import (
    EngineConfig,
    ManualCut,
    ManualPreview,
    SetAuto,
    SetContentEnabled,
    SetLock,
    SetShadow,
)
from cutcut.core.runtime import CoreRuntime, Executor
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

log = logging.getLogger(__name__)

STATE_EVERY_MS: Final = 100  # 10 Hz (docs/design/gui-konsept.md)
METERS_EVERY_MS: Final = 50  # 20 Hz (spec 10.2)
LOG_KEEP: Final = 200
TUNING_KEY: Final = "studio.tuning"
HISTORY_KEEP: Final = 200
# The multiview is set up once and not changed during use, so it is checked at start-up
# (as soon as the ATEM can be read, or after this long without it) and on request (D-056).
MULTIVIEW_STARTUP_WAIT_MS: Final = 30_000


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
        self._load_devices()
        self._load_tuning()
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
        self._mv_errors = ""
        self._mv_seen_error = False
        self.history: dict[str, SessionRecord] = {}

    # -- configuration --------------------------------------------------------------------

    def _show_for(self, participants: int) -> ShowConfig:
        for show in self.deps.site.shows.values():
            if len(show.participants) == participants:
                return show
        raise CommandError(f"Studioet har ikke oppsett for {participants} personer.")

    def _merged(self, show: ShowConfig) -> ShowConfig:
        """The show with the technician's preset, switches and fine tuning applied."""
        return self._merged_with(show, self.preset, self.features, self.overrides)

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
        if not self._mv_checked and (
            self._mv_readback() is not None or now - self._started_ms >= MULTIVIEW_STARTUP_WAIT_MS
        ):
            self._mv_checked = True
            self._check_multiview()
        return result

    # -- multiview (D-055) ---------------------------------------------------------------

    def _mv_readback(self) -> MultiviewReadback | None:
        reader = getattr(self.deps.executor, "multiview_readback", None)
        return reader() if callable(reader) else None

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
        self, level: Literal["info", "warn", "error"], code: str, msg: str, for_user: bool = False
    ) -> None:
        self._alert_seq += 1
        rec = AlertRecord(self._alert_seq, level, code, msg, self.deps.clock.now(), for_user)
        self.alerts.append(rec)
        del self.alerts[:-50]
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
            ),
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
