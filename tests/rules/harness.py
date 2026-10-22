"""Drive the engine with scripted speech, tick by tick, without any equipment.

h = Harness(participants=2)
h.talk("P2"); h.run(1500)
assert h.program == "CU:P2"
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from cutcut.common.config import effective_rules, example_site_dir, load_rule_presets, load_site
from cutcut.common.ids import CameraId, MicId, ParticipantId, RuleId, SourceId
from cutcut.common.models import Decision
from cutcut.common.models.show import ShowConfig
from cutcut.core.engine import Engine
from cutcut.core.inputs import (
    AtemReadback,
    Command,
    ContentState,
    EngineConfig,
    Inputs,
    MicFrame,
    TileFrame,
)
from cutcut.core.intents import DirectCut, Intent, SetPreview, Take
from cutcut.core.shots import camera_of

TICK_MS = 30
SHOW_IDS = {1: "solo", 2: "samtale", 3: "panel-3", 4: "panel-4"}


@dataclass
class Voice:
    talking: bool = False
    dominance_db: float = 12.0
    vad: float = 0.9
    stopped_at: int = -(10**9)
    pitch_falling: bool = False
    muted: bool = False
    leak: bool = False
    laughing: bool = False


def make_show(
    participants: int,
    *,
    wide: bool = False,
    features: dict[str, Any] | None = None,
    overrides: dict[str, float] | None = None,
    preset: str = "standard",
) -> ShowConfig:
    site = load_site(example_site_dir())
    show = site.shows[SHOW_IDS[participants]]
    data: dict[str, Any] = show.model_dump(mode="json")
    if wide:
        data["cameras"]["C7"] = {
            "driver": "obsbot",
            "ip": "10.10.10.27",
            "atem_input": 7,
            "role": "wide",
        }
    data["features"] = {**data["features"], **(features or {})}
    data["rules_override"] = overrides or {}
    data["rules_preset"] = preset
    return ShowConfig.model_validate(data)


@dataclass
class Harness:
    participants: int = 2
    wide: bool = False
    features: dict[str, Any] = field(default_factory=dict)
    overrides: dict[str, float] = field(default_factory=dict)
    preset: str = "standard"
    shadow: bool = False

    def __post_init__(self) -> None:
        self.show = make_show(
            self.participants,
            wide=self.wide,
            features=self.features,
            overrides=self.overrides,
            preset=self.preset,
        )
        self.rules = effective_rules(self.show, load_rule_presets())
        self.engine = Engine(EngineConfig.from_show(self.show, self.rules), shadow=self.shadow)
        self.now = 0
        self.voices = {p.id: Voice() for p in self.show.participants}
        self.laptop = Voice()
        self.decisions: list[Decision] = []
        self.intents: list[tuple[int, Intent]] = []
        self.audio_age_ms = 0
        self.audio_lost = False
        self.moving: set[CameraId] = set()
        self.tracking: set[CameraId] = set()
        self.vision: dict[SourceId, TileFrame] | None = None
        self.atem: AtemReadback | None = None
        self.content: ContentState | None = None
        self.pending: list[Command] = []
        self.violations: list[str] = []

    # -- script ---------------------------------------------------------------------------

    def talk(self, pid: str, *, dominance_db: float = 12.0, vad: float = 0.9) -> None:
        v = self.voices[ParticipantId(pid)]
        v.talking, v.dominance_db, v.vad = True, dominance_db, vad

    def stop(self, pid: str, *, pitch_falling: bool = False) -> None:
        v = self.voices[ParticipantId(pid)]
        if v.talking:
            v.stopped_at = self.now
        v.talking = False
        v.pitch_falling = pitch_falling

    def stop_all(self) -> None:
        for pid in self.voices:
            self.stop(pid.value)

    def voice(self, pid: str) -> Voice:
        return self.voices[ParticipantId(pid)]

    def command(self, cmd: Command) -> None:
        self.pending.append(cmd)

    def run(self, ms: int) -> None:
        end = self.now + ms
        while self.now < end:
            self.now += TICK_MS
            self._tick()

    def phrases(self, pid: str, total_ms: int, phrase_ms: int = 3000, pause_ms: int = 400) -> None:
        """Talk in phrases with natural pauses between them."""
        end = self.now + total_ms
        while self.now < end:
            self.talk(pid)
            self.run(min(phrase_ms, end - self.now))
            if self.now >= end:
                break
            self.stop(pid, pitch_falling=True)
            self.run(min(pause_ms, end - self.now))
        self.talk(pid)

    def _frame(self, v: Voice) -> MicFrame:
        if v.talking:
            return MicFrame(
                vad=v.vad,
                level_db=-20,
                dominance_db=v.dominance_db,
                pause_ms=0,
                in_main_mix=not v.muted,
                leak=v.leak,
                laughter=v.laughing,
            )
        pause = min(self.now - v.stopped_at, 10_000)
        return MicFrame(
            vad=0.05,
            level_db=-60,
            dominance_db=0.0,
            pause_ms=pause,
            phrase_end=pause < 10_000,
            pitch_falling=v.pitch_falling,
            in_main_mix=not v.muted,
            laughter=v.laughing,
        )

    def _tick(self) -> None:
        mics = {self.show.participant(pid).mic: self._frame(v) for pid, v in self.voices.items()}
        mics[MicId.M5] = self._frame(self.laptop)
        if self.audio_lost:
            self.audio_age_ms += TICK_MS
        else:
            self.audio_age_ms = 0
        inp = Inputs(
            now_ms=self.now,
            mics={} if self.audio_lost else mics,
            audio_age_ms=self.audio_age_ms,
            vision=self.vision,
            content=self.content,
            atem=self.atem,
            cameras_moving=frozenset(self.moving),
            cameras_tracking=frozenset(self.tracking),
            commands=tuple(self.pending),
        )
        self.pending = []
        result = self.engine.step(inp)
        for d in result.decisions:
            if d.action == "cut" and d.rule is not RuleId.MANUAL:
                cam = camera_of(d.shot, self.show) if d.shot != "AUDIO_ONLY" else None
                if cam is not None and cam in self.moving:
                    self.violations.append(f"{self.now}: cut to moving {cam} ({d.rule})")
        self.decisions.extend(result.decisions)
        self.intents.extend((self.now, i) for i in result.intents)

    # -- queries --------------------------------------------------------------------------

    @property
    def program(self) -> str:
        return self.engine.program

    def cuts(self, since: int = 0) -> list[Decision]:
        return [
            d
            for d in self.decisions
            if d.action == "cut" and d.mono_ms >= since and d.switch is None
        ]

    def cut_rules(self, since: int = 0) -> list[RuleId]:
        return [d.rule for d in self.cuts(since)]

    def waits(self, blocked_by: RuleId | None = None) -> list[Decision]:
        return [
            d
            for d in self.decisions
            if d.action == "wait" and (blocked_by is None or d.blocked_by is blocked_by)
        ]

    def last_cut(self) -> Decision:
        cuts = self.cuts()
        assert cuts, "no cuts"
        return cuts[-1]

    def intents_of(self, kind: type) -> list[tuple[int, Intent]]:
        return [(t, i) for t, i in self.intents if isinstance(i, kind)]

    def cut_times(self) -> list[int]:
        return [t for t, i in self.intents if isinstance(i, Take | DirectCut)]

    def preview_times(self) -> list[int]:
        return [t for t, _ in self.intents_of(SetPreview)]


def all_rules(decisions: Iterable[Decision]) -> set[RuleId]:
    return {d.rule for d in decisions}


WARMUP_MS = 3000  # past T3 for the opening shot


def started(participants: int = 2, **kw: Any) -> Harness:
    h = Harness(participants=participants, **kw)
    h.run(WARMUP_MS)
    return h
