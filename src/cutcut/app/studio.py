"""The studio as one service: engine, session, recorder, alerts and live data for the screens.

All state lives here, not in the screens (12.5): the API reads it and sends commands to it,
and the screens get a full snapshot on connect and changes afterwards. The same class runs in
the studio (real devices) and in ``cutcut sim`` (fake devices and synthetic talkers).
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, Literal, Protocol

from cutcut import __version__
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
from cutcut.common.config import RulePresets, ShowTypes, Site, effective_rules
from cutcut.common.ids import MicId, RuleId, is_shot
from cutcut.common.models.decision import Decision
from cutcut.common.models.session import RecordingStatus, ShowChoice, StartedBy, TouchStep, User
from cutcut.common.models.show import RulesPreset, ShowConfig
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

log = logging.getLogger(__name__)

STATE_EVERY_MS: Final = 100  # 10 Hz (docs/design/gui-konsept.md)
METERS_EVERY_MS: Final = 50  # 20 Hz (spec 10.2)
LOG_KEEP: Final = 200
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


@dataclass
class Studio:
    deps: StudioDeps
    hub: Hub = field(default_factory=Hub)

    def __post_init__(self) -> None:
        self.sessions = SessionManager()
        self.show = self._show_for(self.sessions.default_show.participants)
        self.preset: RulesPreset = self.show.rules_preset
        self.features = self.show.features
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

    # -- configuration --------------------------------------------------------------------

    def _show_for(self, participants: int) -> ShowConfig:
        for show in self.deps.site.shows.values():
            if len(show.participants) == participants:
                return show
        raise CommandError(f"Studioet har ikke oppsett for {participants} personer.")

    def _make_engine(self, show: ShowConfig) -> Engine:
        data = show.model_dump()
        data.update(rules_preset=self.preset, features=self.features.model_dump())
        merged = ShowConfig.model_validate(data)
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
        return result

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
                name=self.deps.site.devices.studio,
                simulator=self.deps.simulator,
                version=__version__,
                show_types={k: v.name for k, v in self.deps.show_types.types.items()},
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
            recording=RecordingInfo(
                pearl=self.deps.recorder.state.value,
                duration_s=session.recording.duration_s if session else 0,
                started_by=session.recording.started_by if session else None,
            ),
            rules=RulesInfo(preset=self.preset, features=self.features.model_dump()),
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

    def _reconfigure(self) -> None:
        """ADR-0011: switches and presets change live, from the next tick."""
        data = self.show.model_dump()
        data.update(rules_preset=self.preset, features=self.features.model_dump())
        merged = ShowConfig.model_validate(data)
        rules = effective_rules(merged, self.deps.presets)
        self.engine.set_config(EngineConfig.from_show(merged, rules))

    def _check_shot(self, shot: str) -> None:
        if not is_shot(shot):
            raise CommandError(f"Ukjent bilde: {shot}")
        if shot.startswith("CU:") and shot[3:] not in {p.id.value for p in self.show.participants}:
            raise CommandError(f"{shot[3:]} er ikke med i dette oppsettet.")

    def rules_info(self) -> dict[str, Any]:
        return {
            "preset": self.preset,
            "values": self.engine.rules.model_dump(),
            "ids": [r.value for r in RuleId],
        }
