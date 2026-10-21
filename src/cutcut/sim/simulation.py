"""Run the real engine and runtime against synthetic talkers and fake devices."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from cutcut.common.clock import FakeClock
from cutcut.common.config import (
    effective_rules,
    example_site_dir,
    load_rule_presets,
    load_site,
)
from cutcut.common.ids import CameraId, ParticipantId, RuleId, SourceId
from cutcut.common.models.decision import Decision
from cutcut.common.models.show import ShowConfig
from cutcut.core.engine import Engine, StepResult
from cutcut.core.inputs import (
    Command,
    ContentState,
    EngineConfig,
    ManualCut,
    SetAuto,
    SetContentEnabled,
    SetLock,
    StartShow,
)
from cutcut.core.intents import DirectCut, Take
from cutcut.core.runtime import TICK_MS, CoreRuntime
from cutcut.core.shots import camera_of
from cutcut.sim.fakes import FakeAtem, FakePearl
from cutcut.sim.scenario import Expect, Fault, Scenario, Step
from cutcut.sim.voices import Conversation, Voices


def build_show(
    show_id: str,
    *,
    wide: bool = False,
    features: dict[str, bool] | None = None,
    preset: str = "standard",
) -> ShowConfig:
    site = load_site(example_site_dir())
    data: dict[str, Any] = site.shows[show_id].model_dump(mode="json")
    if wide:
        data["cameras"]["C7"] = {
            "driver": "obsbot",
            "ip": "10.10.10.27",
            "atem_input": 7,
            "role": "wide",
        }
    data["features"] = {**data["features"], **(features or {})}
    data["rules_preset"] = preset
    return ShowConfig.model_validate(data)


@dataclass
class Simulation:
    show: ShowConfig
    seed: int = 1
    conversation: bool = False
    shadow: bool = False
    on_tick: Callable[[Simulation, StepResult], None] | None = None

    clock: FakeClock = field(init=False)
    voices: Voices = field(init=False)
    talk_model: Conversation | None = field(init=False)
    atem: FakeAtem = field(init=False)
    pearl: FakePearl = field(init=False)
    runtime: CoreRuntime = field(init=False)
    content: ContentState | None = field(init=False, default=None)
    moving: set[CameraId] = field(init=False, default_factory=set)
    audio_lost: bool = field(init=False, default=False)
    decisions: list[Decision] = field(init=False, default_factory=list)
    cut_times: list[int] = field(init=False, default_factory=list)
    violations: list[str] = field(init=False, default_factory=list)
    content_violations: list[str] = field(init=False, default_factory=list)
    _content_lost_on_air: int | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.clock = FakeClock()
        self.voices = Voices(self.show, seed=self.seed)
        self.talk_model = Conversation(self.voices, seed=self.seed) if self.conversation else None
        self.atem = FakeAtem()
        self.pearl = FakePearl()
        rules = effective_rules(self.show, load_rule_presets())
        engine = Engine(EngineConfig.from_show(self.show, rules), shadow=self.shadow)
        self.runtime = CoreRuntime(engine, self.clock, self.atem, on_step=self._after_step)

    @property
    def engine(self) -> Engine:
        return self.runtime.engine

    @property
    def now(self) -> int:
        return self.clock.mono_ms()

    def command(self, cmd: Command) -> None:
        self.runtime.command(cmd)

    def tick(self) -> None:
        self.clock.advance(TICK_MS)
        now = self.clock.mono_ms()
        if self.talk_model is not None:
            self.talk_model.update(now)
        self.pearl.update(now)
        if not self.audio_lost:
            self.runtime.feed_audio(self.voices.frames(now))
        self.runtime.feed_content(self.content)
        self.runtime.feed_atem(self.atem.readback())
        self.runtime.feed_cameras_moving(frozenset(self.moving))
        self.runtime.tick()

    def _after_step(self, result: StepResult) -> None:
        now = self.clock.mono_ms()
        for d in result.decisions:
            if d.action == "cut" and d.rule is not RuleId.MANUAL:
                cam = camera_of(d.shot, self.show) if d.shot != "AUDIO_ONLY" else None
                if cam is not None and cam in self.moving:
                    self.violations.append(f"{now} ms: cut to moving camera {cam.value}")
        self.decisions.extend(result.decisions)
        lost = self.content in (None, ContentState.NO_SIGNAL)
        if self.engine.program == "CONTENT" and lost:
            if self._content_lost_on_air is None:
                self._content_lost_on_air = now
            elif now - self._content_lost_on_air > 1000:  # 10.4: removed within 1 s
                self.content_violations.append(f"{now} ms: CONTENT on air without signal")
        else:
            self._content_lost_on_air = None
        if any(isinstance(i, Take | DirectCut) for i in result.intents):
            self.cut_times.append(now)
        if self.on_tick is not None:
            self.on_tick(self, result)

    def run(self, ms: int) -> None:
        end = self.now + ms
        while self.now < end:
            self.tick()


# -- scenarios ----------------------------------------------------------------------------


@dataclass
class ScenarioResult:
    scenario: Scenario
    simulation: Simulation
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


def _apply_step(
    sim: Simulation, step: Step, end_events: list[tuple[int, Callable[[], None]]]
) -> None:
    now = sim.now
    until = None if step.for_ is None else now + int(step.for_ * 1000)
    v = sim.voices
    if step.talk is not None:
        pid = step.talk
        v.talk(pid, now, step.dominance)
        if until is not None:
            end_events.append((until, lambda: v.stop(pid, sim.now, step.pitch_falling)))
    if step.stop is not None:
        v.stop(step.stop, now, step.pitch_falling)
    if step.content is not None:
        sim.content = step.content
    if step.laptop_audio is not None:
        v.laptop.talking = step.laptop_audio
        if until is not None and step.laptop_audio:
            end_events.append((until, lambda: setattr(v.laptop, "talking", False)))
    if step.laugh:
        for pid in step.laugh:
            v.laugh(pid, now, int((step.for_ or 3) * 1000))
    if step.mute is not None:
        v.voices[step.mute].muted = True
        if until is not None:
            muted = step.mute
            end_events.append((until, lambda: setattr(v.voices[muted], "muted", False)))
    if step.unmute is not None:
        v.voices[step.unmute].muted = False
    commands: dict[str, Command] = {
        "auto_off": SetAuto(on=False),
        "auto_on": SetAuto(on=True),
        "lock": SetLock(on=True),
        "unlock": SetLock(on=False),
        "content_off": SetContentEnabled(enabled=False),
        "content_on": SetContentEnabled(enabled=True),
    }
    if step.command is not None:
        sim.command(commands[step.command])
    if step.manual_cut is not None:
        sim.command(ManualCut(step.manual_cut))
    if step.operator_cut is not None:
        sim.atem.operator_cut(SourceId(step.operator_cut))


def _apply_fault(
    sim: Simulation, fault: Fault, end_events: list[tuple[int, Callable[[], None]]], on: bool
) -> None:
    match fault.kind:
        case "audio_lost":
            sim.audio_lost = on
        case "atem_down":
            sim.atem.online = not on
        case "companion_down":
            sim.atem.companion_online = not on
        case "camera_moving":
            if fault.camera is not None:
                (sim.moving.add if on else sim.moving.discard)(fault.camera)
        case "video_down":
            sim.content = None if on else sim.content
        case "pearl_fail":
            if on:
                sim.pearl.fail()
    if on and fault.for_ is not None:
        end_events.append(
            (sim.now + int(fault.for_ * 1000), lambda: _apply_fault(sim, fault, end_events, False))
        )


def run_scenario(
    sc: Scenario,
    *,
    on_tick: Callable[[Simulation, StepResult], None] | None = None,
) -> ScenarioResult:
    show = build_show(sc.show, wide=sc.wide, features=sc.features, preset=sc.preset)
    sim = Simulation(show, seed=sc.seed, conversation=sc.conversation, on_tick=on_tick)
    if sc.start_show:
        sim.command(StartShow())
    pending = sorted(
        [(int(s.at * 1000), 0, i) for i, s in enumerate(sc.script)]
        + [(int(f.at * 1000), 1, i) for i, f in enumerate(sc.faults)]
    )
    end_events: list[tuple[int, Callable[[], None]]] = []
    end = int(sc.duration_s * 1000)
    while sim.now < end:
        while pending and pending[0][0] <= sim.now:
            _, kind, idx = pending.pop(0)
            if kind == 0:
                _apply_step(sim, sc.script[idx], end_events)
            else:
                _apply_fault(sim, sc.faults[idx], end_events, True)
        due = [e for e in end_events if e[0] <= sim.now]
        for event in due:
            end_events.remove(event)
            event[1]()
        sim.tick()
    return ScenarioResult(sc, sim, check(sc, sim))


def check(sc: Scenario, sim: Simulation) -> list[str]:
    failures: list[str] = []
    cuts = [d for d in sim.decisions if d.action == "cut"]
    for e in sc.expect:
        failures.extend(_check_one(e, sim, cuts))
    return failures


def _check_one(e: Expect, sim: Simulation, cuts: list[Decision]) -> list[str]:
    out = []
    if e.rule is not None:
        pool = (
            sim.decisions
            if e.action == "any"
            else [d for d in sim.decisions if d.action == e.action]
        )
        hits = [d for d in pool if d.rule is e.rule]
        if e.between_s is not None:
            lo, hi = (int(x * 1000) for x in e.between_s)
            hits = [d for d in hits if lo <= d.mono_ms <= hi]
        if not hits:
            where = f" between {e.between_s}" if e.between_s else ""
            out.append(f"expected {e.action} with rule {e.rule.value}{where}")
    if e.never == "cut_to_moving_camera" and sim.violations:
        out.extend(sim.violations)
    if e.never == "cuts_faster_than_1s":
        times = sim.cut_times
        fast = [(a, b) for a, b in itertools.pairwise(times) if b - a < 1000]
        if fast:
            out.append(f"cuts less than 1 s apart: {fast[:3]}")
    if e.never == "content_on_air_without_signal" and sim.content_violations:
        out.extend(sim.content_violations)
    if e.min_cuts is not None and len(cuts) < e.min_cuts:
        out.append(f"only {len(cuts)} cuts, expected at least {e.min_cuts}")
    if e.max_cuts_per_10min is not None:
        minutes = max(sim.now / 60000, 1e-9)
        rate = len(cuts) / minutes * 10
        if rate > e.max_cuts_per_10min:
            out.append(f"{rate:.1f} cuts per 10 min, expected at most {e.max_cuts_per_10min}")
    later = {d.shot for d in cuts if d.mono_ms >= e.after_s * 1000}
    if e.shot_seen is not None and e.shot_seen not in later:
        out.append(f"shot {e.shot_seen} never on program after {e.after_s} s")
    if e.shot_not_seen is not None and e.shot_not_seen in later:
        out.append(f"shot {e.shot_not_seen} was on program after {e.after_s} s")
    if e.program_at_end is not None and sim.engine.program != e.program_at_end:
        out.append(f"program at end is {sim.engine.program}, expected {e.program_at_end}")
    return out


__all__ = ["ParticipantId", "ScenarioResult", "Simulation", "build_show", "run_scenario"]
