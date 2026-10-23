"""The rule engine (spec 5). Pure and deterministic (I3): no clock, no I/O, no randomness.

One call to ``Engine.step(inputs)`` per 30 ms tick returns the decisions to log and the
intents for the devices. The priority order is spec 5.2:

1. Override (manual cut, LOCK, AUTO off, ATEM changed by a person) – always wins (I5).
2. Safety (S) – audio lost, content lost, minimum shot length, one cut per second.
3. Content (CT).
4. Crosstalk and laughter (T5, B2, B4).
5. Speaker (T2, T4) – via preview, taken at a cut point (5.9, 5.10).
6. Variation (T7, B5).
7. Silence (T8, B3).

Hold and release (5.11) filter everything except override and lost content.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal

from cutcut.common.config.rules import RuleParams
from cutcut.common.ids import (
    AUDIO_ONLY,
    BIRD,
    CONTENT,
    QUAD3C,
    QUAD4,
    WIDE,
    CameraId,
    MicId,
    Mode,
    ParticipantId,
    RuleId,
    SourceId,
    close_up,
    is_layout,
    pip_content,
    pip_two,
    shot_participants,
)
from cutcut.common.models.decision import Decision, DecisionAction
from cutcut.common.models.show import FeatureMode, ShowConfig
from cutcut.core import shots
from cutcut.core.content import ContentTracker
from cutcut.core.inputs import (
    EndShow,
    EngineConfig,
    Inputs,
    ManualCut,
    ManualPreview,
    SetAuto,
    SetContentEnabled,
    SetLock,
    SetShadow,
    StartShow,
)
from cutcut.core.intents import (
    DirectCut,
    FrameCamera,
    Intent,
    NudgeCamera,
    PrepareLayout,
    SetCompanionVariable,
    SetPreview,
    ShowAudioOnly,
    SlowZoom,
    StopZoom,
    Take,
)
from cutcut.core.speakers import Speakers

# Time the ATEM gets to show our take before a difference counts as a manual change (I5).
SETTLE_MS = 600
# Audio must be back this long before AUTO resumes after S4.
AUDIO_RECOVER_MS = 2000
# T9: a pause this long counts as "a short pause" for soft cut timing.
T9_PAUSE_MS = 150
# T7/B5: a pause up to this long is still "inside the answer", so an insert can be taken there.
VARIATION_PAUSE_MAX_MS = 1500
# H4: the return shot goes to preview this long before the insert ends (preview first, 5.9).
RETURN_PREVIEW_MS = 600
# 5.9/10.4: a new speaker is armed on preview at half T2, but at least this long before the cut
# can come, so preview leads program by ≥ 300 ms also with short T2 (Energisk).
PREVIEW_LEAD_MS = 350
# 5.9: the reserve shot goes to preview only after this long without a candidate, so it does
# not take the PV1 slot right before the next speaker.
IDLE_FALLBACK_MS = 1500
# 10.4: a speaker cut shows the new shot on preview at least this long first (unless K3).
MIN_PREVIEW_LEAD_MS = 300
# V1: a mouth this active counts as moving, and stays «moving» this long after.
MOUTH_ON = 0.3
MOUTH_RECENT_MS = 300
# V4: where a face should sit in a close-up, the step size, and how often.
V4_TARGET_X = 0.5
V4_TARGET_Y = 0.42
V4_STEP = 0.1
V4_EVERY_MS = 2000
# F-1: a switch in shadow logs the same «would have» again only after this long.
SHADOW_REPEAT_MS = 2000
# 5.6: the base-mode shots a layout may replace (speaker, crosstalk, ping-pong, and the
# group shot when three or more talk). Content, inserts, silence and laughter stay.
LAYOUT_REPLACES = frozenset({RuleId.T2, RuleId.H1, RuleId.T4, RuleId.T5, RuleId.T6, RuleId.B2})

Timing = Literal["speaker", "insert", "soft", "now", "return"]


class PreviewState(StrEnum):
    """Spec 5.9."""

    IDLE = "IDLE"
    ARMED = "ARMED"
    READY = "READY"


@dataclass(frozen=True)
class Proposal:
    shot: str
    rule: RuleId
    timing: Timing
    reason: str
    measures: dict[str, float] = field(default_factory=dict)
    confirmed: bool = True  # speaker proposals arm at half T2 and are confirmed at T2
    speaker: ParticipantId | None = None
    insert_ms: int | None = None  # inserts (reaction, bird) return after this long (H4)
    return_to: str | None = None  # where an insert returns to; default: the shot it replaced


@dataclass
class Insert:
    """A short reaction or bird's-eye shot that returns to the same speaker (H4)."""

    rule: RuleId
    return_to: str
    speaker: ParticipantId | None
    end_ms: int


@dataclass
class StepResult:
    decisions: list[Decision]
    intents: list[Intent]


def _sec(ms: float) -> str:
    return f"{ms / 1000:.2f}".replace(".", ",") + " s"


class Engine:
    def __init__(
        self,
        config: EngineConfig,
        *,
        now_ms: int = 0,
        wall_clock: datetime | None = None,
        shadow: bool = False,
    ) -> None:
        self.config = config
        self.wall_origin = wall_clock or datetime(2026, 1, 1).astimezone()
        self.origin_ms = now_ms
        self.speakers = Speakers.for_show(config.show)
        self.shadow = shadow
        self.auto = True
        self.lock = False
        self.content_enabled = True
        self.audio_only = False
        self.mode = Mode.for_show(len(config.show.participants), False)
        fallback = shots.fallback_shot(self.mode, config.show, config.features)
        self.program = fallback
        self.program_since = now_ms
        self.previous_program: str | None = None
        self.previous_program_end = -(10**9)
        self.last_cut_ms = -(10**9)
        self.preview: str | None = None
        self.preview_since = -(10**9)
        self.pv_state = PreviewState.IDLE
        self.candidate: Proposal | None = None
        self.ready_since: int | None = None
        self.quiet_until = -(10**9)
        self.s4_paused = False
        self.audio_back_since: int | None = None
        self.insert: Insert | None = None
        self.speaker_on_air: ParticipantId | None = None
        self.speaker_on_air_since = now_ms
        self.last_variation_ms = now_ms
        self.variation_count = 0
        self.settle_until = -(10**9)
        self.manual_preview: str | None = None
        self.last_wait: tuple[str, RuleId | None] | None = None
        self.vars: dict[str, str] = {}
        self._cut_rule: RuleId | None = None
        self.idle_since: int | None = None
        self.bird_ms_total = 0
        self.content = ContentTracker()
        self.failed_switches: set[str] = set()  # F-1: the studio moves these to shadow
        self.layout_ended: dict[str, int] = {}
        # F1–F3, Z1–Z3: which framing each camera has, cameras waiting to be reframed, and
        # the slow zoom that runs (shot, camera, start)
        self.framing: dict[CameraId, str] = {}
        self.reframe_until: dict[CameraId, int] = {}
        self._reframe_pending: set[CameraId] = set()
        self._on_air_before: set[CameraId] = set()
        self._zoomed: set[CameraId] = set()
        self._f3_waiting: set[CameraId] = set()
        # V1, V3, V4, V5, PV3, R1: what the video layer has seen
        self._mouth_at: dict[ParticipantId, int] = {}
        self._reacts: dict[ParticipantId, deque[tuple[int, float]]] = {}
        self._still_since: dict[SourceId, int] = {}
        self._v4_at: dict[CameraId, int] = {}
        self._leak_noted: set[ParticipantId] = set()
        self._r2_noted: ParticipantId | None = None
        self.last_reaction_ms = -(10**9)
        self._zoom: tuple[str, CameraId, int] | None = None
        self._shadow_seen: dict[tuple[str, str, str, RuleId], int] = {}
        self.last_bird_ms = -(10**9)
        self._now = now_ms
        self._decisions: list[Decision] = []
        self._intents: list[Intent] = []
        self._seq = 0

    # -- public ---------------------------------------------------------------------------

    @property
    def rules(self) -> RuleParams:
        return self.config.rules

    @property
    def show(self) -> ShowConfig:
        return self.config.show

    @property
    def paused(self) -> bool:
        return (
            not self.auto
            or self.lock
            or self.audio_only
            or self.s4_paused
            or self._now < self.quiet_until
        )

    def settings(self) -> dict[str, bool]:
        """What must survive a restart (K-9). Shots and timers do not: after a restart the
        engine takes what the ATEM shows and waits ``manual_quiet_s`` before cutting."""
        return {
            "auto": self.auto,
            "lock": self.lock,
            "content_enabled": self.content_enabled,
            "audio_only": self.audio_only,
            "shadow": self.shadow,
        }

    def restore(self, settings: dict[str, bool], now_ms: int) -> None:
        self.auto = bool(settings.get("auto", True))
        self.lock = bool(settings.get("lock", False))
        self.content_enabled = bool(settings.get("content_enabled", True))
        self.audio_only = bool(settings.get("audio_only", False))
        self.shadow = bool(settings.get("shadow", self.shadow))
        self.quiet_until = now_ms + int(self.rules.manual_quiet_s * 1000)

    def set_config(self, config: EngineConfig) -> None:
        """Takes effect from the next tick (ADR-0011: switches can change live). A failed
        switch that the technician (or the studio) has moved runs again (F-1)."""
        old = self.config.features
        self.failed_switches -= {
            n for n in self.failed_switches if config.features.mode(n) != old.mode(n)
        }
        self.config = config

    def step(self, inp: Inputs) -> StepResult:
        self._now = now = inp.now_ms
        self._decisions, self._intents = [], []
        self.speakers.update(now, inp.mics, self.rules)
        laptop = inp.mics.get(MicId.M5)
        laptop_audio = laptop is not None and laptop.vad >= self.rules.T1_vad_threshold
        self._commands(inp)
        self.content.update(
            now,
            inp.content,
            laptop_audio,
            self.content_enabled and self.config.features.content,
            self.rules,
        )
        self._reconcile(inp)
        self._observe(inp)
        self.mode = Mode.for_show(len(self.show.participants), self.content.active, self.audio_only)

        if self.audio_only:
            self._audio_only()
        elif not self._safety(inp) and not self.paused:
            self._auto(inp)
            self._cameras(inp)
        self._companion_variables()
        return StepResult(self._decisions, self._intents)

    # -- commands and override (5.2 step 1) -----------------------------------------------

    def _commands(self, inp: Inputs) -> None:
        for cmd in inp.commands:
            match cmd:
                case SetAuto(on=on):
                    self.auto = on
                    self._decide(
                        "hold", self.program, RuleId.MANUAL, f"AUTO {'på' if on else 'av'}"
                    )
                case SetLock(on=on):
                    self.lock = on
                    self._decide("hold", self.program, RuleId.MANUAL, f"LÅS {'på' if on else 'av'}")
                case ManualCut(shot=shot):
                    self._take_direct(shot, RuleId.MANUAL, "Manuelt kutt", force=True)
                    self.quiet_until = self._now + int(self.rules.manual_quiet_s * 1000)
                case ManualPreview(shot=shot):
                    self.manual_preview = shot
                case SetContentEnabled(enabled=enabled):
                    self.content_enabled = enabled
                case SetShadow(on=on):
                    self.shadow = on
                case StartShow(audio_only=audio_only):
                    self.audio_only = audio_only
                    if not audio_only:
                        self._opening()
                case EndShow():
                    self.audio_only = False
                    self.insert = None

    def _reconcile(self, inp: Inputs) -> None:
        """ATEM is the truth (ADR-0004, I5). A difference we did not cause is a person."""
        if self.shadow or inp.atem is None or self._now < self.settle_until:
            return
        actual = shots.shot_for(inp.atem.program, self.show, inp.atem.program_layout)
        if actual is None or actual == self.program:
            return
        if self.audio_only and inp.atem.program is SourceId.SUPERSOURCE:
            return
        self._set_program(actual)
        self.quiet_until = self._now + int(self.rules.manual_quiet_s * 1000)
        self.candidate = None
        self.pv_state = PreviewState.IDLE
        self._decide(
            "hold",
            actual,
            RuleId.MANUAL,
            f"Bildet ble endret utenfor CutCut; venter {_sec(self.rules.manual_quiet_s * 1000)}",
        )

    # -- safety (5.7) -----------------------------------------------------------------------

    def _safety(self, inp: Inputs) -> bool:
        """Returns True if a safety rule took control this tick."""
        lost_ms = int(self.rules.S4_audio_lost_s * 1000)
        if inp.audio_age_ms >= lost_ms:
            self.audio_back_since = None
            if not self.s4_paused:
                self.s4_paused = True
                self.candidate = None
                self.pv_state = PreviewState.IDLE
                self._decide(
                    "hold",
                    self.program,
                    RuleId.S4,
                    f"Ingen lyd på {_sec(inp.audio_age_ms)}; AUTO på pause",
                    {"audio_age_ms": inp.audio_age_ms},
                )
            target = shots.fallback_shot(self.mode, self.show, self.config.features)
            if self.program != target:
                self._take_direct(target, RuleId.S4, "Ingen lyd: til reservebildet")
            return True
        if self._shows_content(self.program) and self.content.lost():
            # CT6: the laptop disappeared while on air – cut away at once (PV4), only S3 holds
            target = self._speaker_shot() or shots.fallback_shot(
                self.mode, self.show, self.config.features
            )
            self._take_direct(target, RuleId.CT6, "Content-signalet forsvant")
            return True
        if self.s4_paused:
            if self.audio_back_since is None:
                self.audio_back_since = self._now
            if self._now - self.audio_back_since >= AUDIO_RECOVER_MS:
                self.s4_paused = False
                self._decide("hold", self.program, RuleId.S4, "Lyden er tilbake; AUTO fortsetter")
            return True
        return False

    def _cut_allowed(self) -> bool:
        """S3: never more than one cut per second, whatever the rule."""
        return self._now - self.last_cut_ms >= int(self.rules.S3_min_cut_gap_s * 1000)

    def _min_shot_ms(self) -> int:
        """T3, plus extra for a guest so answers can stand (5.12)."""
        ms = int(self.rules.T3_min_shot_s * 1000)
        speaker = shots.speaker_of(self.program)
        if speaker is not None and not self.speakers.get(speaker).host:
            ms += int(self.rules.T3_guest_extra_s * 1000)
        if is_layout(self.program):
            ms = max(ms, int(self.rules.L_min_s * 1000))  # 5.6: a layout stands at least 6 s
        return ms

    def _eligible(self, shot: str, inp: Inputs) -> RuleId | None:
        """Why a shot cannot be used right now, or None if it can (S1, S2, S6)."""
        if not shots.available(shot, self.show, self.config.features):
            return RuleId.S2
        if self._shows_content(shot) and not self.content.active:
            return RuleId.CT1
        camera = shots.camera_of(shot, self.show)
        if camera is not None and camera in inp.cameras_moving:
            return RuleId.S1
        if camera is not None and self._now < self.reframe_until.get(camera, -1):
            return RuleId.F2  # just reframed: wait until it has moved and stands still
        video = self._mode("video_confirm")
        if video != "off" and inp.vision is not None and camera is not None:
            tile = inp.vision.get(SourceId(camera.value))
            why = None
            if tile is not None and tile.moving:
                why = RuleId.V5  # the picture moves: not a valid angle until it stands still
            elif tile is not None and not tile.face_ok:
                why = RuleId.S2
            if why is not None:
                if video == "on":
                    return why
                self._shadow_note(
                    "video_confirm", "wait", shot, why, "Videolaget ville holdt igjen bildet"
                )
        speaker = shots.speaker_of(shot)
        if speaker is not None and self.speakers.get(speaker).muted:
            return RuleId.S6
        return None

    # -- automatic cutting --------------------------------------------------------------------

    def _auto(self, inp: Inputs) -> None:
        proposal = self._propose(inp)
        if proposal is None or proposal.shot == self.program:
            self._idle(inp)
            return
        blocked = self._blocked(proposal, inp)
        self._arm(proposal, inp)
        if blocked is not None:
            self._wait(proposal, blocked)
            return
        if not proposal.confirmed:
            return
        if self.pv_state is PreviewState.ARMED:
            self.pv_state = PreviewState.READY
            self.ready_since = self._now
        pv3 = self._pv3(proposal, inp)
        if pv3 is not None:
            self._wait(proposal, pv3)
            return
        if self._cut_point(proposal):
            self._take(proposal)

    def _propose(self, inp: Inputs) -> Proposal | None:
        base: Proposal | None = None
        for rule in (
            self._propose_manual_preview,
            self._propose_content,
            self._propose_crosstalk,
            self._propose_speaker,
            self._propose_insert_return,
            self._propose_reaction,
            self._propose_variation,
            self._propose_silence,
        ):
            base = rule(inp)
            if base is not None:
                break
        return self._layouts(base)

    # -- layouts (5.6, L1–L4) -------------------------------------------------------------

    def _layouts(self, base: Proposal | None) -> Proposal | None:
        """A layout instead of the base-mode shot when L1–L4 say so. Only speaker, crosstalk
        and ping-pong shots (or holding the current shot) are replaced: content, inserts,
        silence, laughter and manual choices stay as base mode decides."""
        mode = self._mode("layouts")
        if mode == "off" or self.audio_only:
            return base
        if base is not None and base.rule not in LAYOUT_REPLACES:
            return base
        try:
            alt = self._layout_for(base)
        except Exception as exc:  # a switch never stops base mode (F-1)
            self._switch_failed("layouts", exc)
            return base
        if alt is None or (base is not None and alt.shot == base.shot):
            return base
        if alt.shot == self.program:
            return None if base is None else alt  # keep the layout that stands
        if not self._layout_free(alt.shot):
            return base
        if mode == "shadow":
            self._shadow_note("layouts", "preview", alt.shot, alt.rule, alt.reason, alt.measures)
            return base
        return alt

    def _layout_free(self, shot: str) -> bool:
        """5.6: the same layout is not used again within ``L_no_repeat_s`` of its end."""
        ended = self.layout_ended.get(shot)
        return ended is None or self._now - ended >= self.rules.L_no_repeat_s * 1000

    def _content_recent(self) -> bool:
        r = self.rules
        return self._shows_content(self.program) or (
            self._now - self.content.last_on_air_end <= r.L1_content_recent_s * 1000
        )

    def _layout_for(self, base: Proposal | None) -> Proposal | None:
        r, now, sw, sp, m = self.rules, self._now, self.show.layouts, self.speakers, self.mode
        n = m.participants or 0
        window = int(r.L3_window_s * 1000)
        recent = sp.recent(now, window)
        speaking = sp.speaking()
        crowd = len(speaking) >= 3 and sp.crosstalk_ms(now) >= r.T5_crosstalk_s * 1000
        # L3 / L4: three or more voices in the last L3_window_s, or crosstalk with three
        if len(recent) >= 3 or crowd:
            measures: dict[str, float] = {"speakers": len(recent), "speaking": len(speaking)}
            why = f"{len(recent)} har snakket siste {r.L3_window_s:g} s"
            if m.content and n == 3 and sw.quad_three_content and self.content.active:
                return Proposal(QUAD3C, RuleId.L4, "soft", why + " og content er aktivt", measures)
            if not m.content and n == 4 and sw.quad_four:
                return Proposal(QUAD4, RuleId.L3, "soft", why, measures)
        # L2: ping-pong (or crosstalk) between two particular people
        if (
            n >= 2
            and sw.pip_two_people
            and base is not None
            and base.rule
            in (
                RuleId.T6,
                RuleId.T5,
            )
        ):
            pair = sorted(recent) if len(recent) == 2 else None
            if pair is None and len(speaking) == 2:
                pair = sorted(t.pid for t in speaking)
            if pair is not None:
                names = " og ".join(self.show.participant(p).name for p in pair)
                return Proposal(
                    pip_two(pair[0], pair[1]),
                    RuleId.L2,
                    "soft",
                    f"Ping-pong mellom {names}",
                    {"turns": len(sp.turns)},
                )
        # L1: the speaker has talked a while and content is active and was just shown
        if m.content and sw.pip_speaker_content and self.content.active and self._content_recent():
            pid = base.speaker if base is not None else None
            if pid is None and base is None:
                on_air = shot_participants(self.program)
                pid = on_air[0] if len(on_air) == 1 else None
            if pid is not None:
                talker = sp.get(pid)
                held = self.program == pip_content(pid) and (
                    talker.speaking or talker.frame.pause_ms <= VARIATION_PAUSE_MAX_MS
                )
                if held or (talker.speaking and talker.run_ms(now) >= r.L1_speaker_s * 1000):
                    name = self.show.participant(pid).name
                    return Proposal(
                        pip_content(pid),
                        RuleId.L1,
                        "soft",
                        f"{name} snakker og content er aktivt",
                        {"run_ms": talker.run_ms(now)},
                        speaker=pid,
                    )
        return None

    def _propose_manual_preview(self, inp: Inputs) -> Proposal | None:
        if self.manual_preview is None:
            return None
        if self.manual_preview == self.program:
            self.manual_preview = None
            return None
        return Proposal(self.manual_preview, RuleId.MANUAL, "soft", "Lagt på preview av operatør")

    def _propose_content(self, inp: Inputs) -> Proposal | None:
        """CT1–CT6 (5.5): new slide, video and laptop audio go to content; static content
        returns to the speaker; never content during crosstalk or laughter."""
        r, c, now = self.rules, self.content, self._now
        if not c.active:
            return None
        sp = self.speakers
        if sp.crosstalk_ms(now) >= r.T5_crosstalk_s * 1000 or sp.laughter_since is not None:
            return None  # CT6
        within_video = c.video_since is not None and now - c.video_since <= r.CT3_video_max_s * 1000
        if c.laptop_audio and within_video:
            return Proposal(CONTENT, RuleId.CT5, "soft", "Lyd fra laptop", {"laptop_audio": 1})
        if within_video and c.video_since is not None:
            return Proposal(
                CONTENT, RuleId.CT3, "soft", "Video på laptop", {"video_ms": now - c.video_since}
            )
        if c.slide_at is not None and now - c.slide_at < r.CT2_hold_s * 1000:
            return Proposal(CONTENT, RuleId.CT2, "soft", "Ny slide", {"slide_ms": now - c.slide_at})
        if self.program == CONTENT:
            if now - self.program_since < r.CT4_return_after_s * 1000:
                return Proposal(CONTENT, RuleId.CT4, "soft", "Content står")
            target = self._speaker_shot()
            if target is None:
                return None  # nobody to return to: silence keeps content (5.1)
            if shots.available(BIRD, self.show, self.config.features):
                return Proposal(
                    BIRD,
                    RuleId.B1,
                    "soft",
                    "Kort fugleperspektiv etter content",
                    speaker=shots.speaker_of(target),
                    insert_ms=int(r.B1_after_content_s * 1000),
                    return_to=target,
                )
            return Proposal(target, RuleId.CT4, "soft", "Tilbake til taleren etter content")
        if (
            r.CT4_revisit_enabled
            and self.insert is None
            and now - c.last_on_air_end >= r.CT4_revisit_every_s * 1000
            and shots.speaker_of(self.program) is not None
        ):
            return Proposal(
                CONTENT,
                RuleId.CT4,
                "insert",
                "Kort besøk på content",
                speaker=shots.speaker_of(self.program),
                insert_ms=int(r.CT4_revisit_s * 1000),
            )
        return None

    def _shows_content(self, shot: str) -> bool:
        return shot == CONTENT or shot.endswith("+CONTENT")

    def _speaker_shot(self) -> str | None:
        """Close-up of whoever holds the floor (talking now, else on air before, else last)."""
        speaking = self.speakers.speaking()
        if speaking:
            best = max(speaking, key=lambda t: (t.score(self.rules), t.host))
            return close_up(best.pid)
        pid = self.speaker_on_air or self.speakers.dominant
        return close_up(pid) if pid is not None else None

    def _opening(self) -> None:
        """B1: the show opens on BIRD for B1_open_s, then the host (5.4, 5.12)."""
        host = next((p.id for p in self.show.participants if p.role == "host"), None)
        if host is None:
            return
        host_shot = close_up(host)
        if shots.available(BIRD, self.show, self.config.features):
            if self.program != BIRD:
                self._take_direct(BIRD, RuleId.B1, "Åpning: fugleperspektiv", force=True)
            self.insert = Insert(
                RuleId.B1, host_shot, host, self._now + int(self.rules.B1_open_s * 1000)
            )
            self._decide("hold", BIRD, RuleId.B1, "Åpning: fugleperspektiv, så verten")
        else:
            self._take_direct(host_shot, RuleId.B1, "Åpning: verten", force=True)

    def _propose_crosstalk(self, inp: Inputs) -> Proposal | None:
        sp, r = self.speakers, self.rules
        speaking = len(sp.speaking())
        if speaking >= 3 and sp.crosstalk_ms(self._now) >= r.B2_crosstalk_s * 1000:
            shot = shots.first_available([BIRD], self.show, self.config.features)
            if shot is not None:
                return Proposal(
                    shot,
                    RuleId.B2,
                    "soft",
                    f"{speaking} snakker samtidig",
                    {"speaking": speaking, "crosstalk_ms": sp.crosstalk_ms(self._now)},
                )
        needed_ms = r.T5_crosstalk_s * 1000
        if speaking == 2 and self._host_backchannel():
            needed_ms = max(needed_ms, r.T4_host_backchannel_s * 1000)  # 5.12
        if speaking >= 2 and sp.crosstalk_ms(self._now) >= needed_ms:
            shot = shots.crosstalk_shot(self.mode, self.show, self.config.features)
            if shot is not None:
                return Proposal(
                    shot,
                    RuleId.T5,
                    "soft",
                    "Krysstale",
                    {"speaking": speaking, "crosstalk_ms": sp.crosstalk_ms(self._now)},
                )
        if sp.laughter_ms(self._now) >= r.B4_laugh_min_s * 1000:
            shot = shots.first_available([BIRD], self.show, self.config.features)
            if shot is not None:
                return Proposal(
                    shot, RuleId.B4, "soft", "Flere ler", {"laughter_ms": sp.laughter_ms(self._now)}
                )
        if sp.pingpong(r) and speaking >= 1:
            shot = shots.pingpong_shot(self.mode, self.show, self.config.features)
            if shot is not None:
                return Proposal(
                    shot,
                    RuleId.T6,
                    "soft",
                    "Mange bytter mellom personer",
                    {"turns": len(sp.turns)},
                )
        # Stay on the group shot while the crosstalk is still going on.
        if (
            self.program in (BIRD, WIDE)
            and speaking >= 2
            and sp.crosstalk_ms(self._now) >= needed_ms
            and self.insert is None
        ):
            return Proposal(self.program, RuleId.T5, "soft", "Krysstale fortsetter")
        return None

    def _host_backchannel(self) -> bool:
        """The host talks over the guest who is on air (5.12: short host interjections)."""
        on_air = self.speaker_on_air
        if on_air is None or self.speakers.get(on_air).host:
            return False
        return any(t.host for t in self.speakers.speaking() if t.pid != on_air)

    def _required_run_ms(self, pid: ParticipantId) -> tuple[int, RuleId, dict[str, float]]:
        """How long a new speaker must talk before a cut (T2 with H1, T4, roles)."""
        r = self.rules
        required = float(r.T2_confirm_ms)
        rule = RuleId.T2
        measures: dict[str, float] = {}
        if self._now - self.last_cut_ms < r.H1_window_s * 1000:
            required *= r.H1_factor
            rule = RuleId.H1
            measures["h1_factor"] = r.H1_factor
        on_air = self.speaker_on_air
        if on_air is not None and on_air != pid and self.speakers.get(on_air).speaking:
            if required < r.T4_ignore_interrupt_s * 1000:
                required = r.T4_ignore_interrupt_s * 1000
                rule = RuleId.T4
            talker, other = self.speakers.get(pid), self.speakers.get(on_air)
            if talker.host and not other.host and required < r.T4_host_backchannel_s * 1000:
                required = r.T4_host_backchannel_s * 1000
                rule = RuleId.T4
                measures["host_backchannel"] = 1
        if self._mouth_moves(pid) and rule in (RuleId.T2, RuleId.H1):
            mode = self._mode("video_confirm")
            if mode == "on":  # V1: the mouth moves in the right camera, so trust the mic sooner
                required *= r.V1_factor
                rule = RuleId.V1
                measures["v1_factor"] = r.V1_factor
            elif mode == "shadow":
                shot = close_up(pid)
                self._shadow_note("video_confirm", "preview", shot, RuleId.V1, "Munnen beveger seg")
        return int(required), rule, measures

    def _propose_speaker(self, inp: Inputs) -> Proposal | None:
        """T2: a new confirmed speaker goes to preview first, then to program (5.9)."""
        speaking = self.speakers.speaking()
        leaks = [t for t in speaking if self._mouth_still(t.pid, t.speaking_since)]
        if leaks:
            mode = self._mode("video_confirm")
            for t in leaks:  # V1: an active mic with a still mouth is leakage, not speech
                why = f"Mic aktiv, men munnen står stille ({self.show.participant(t.pid).name})"
                if mode == "shadow":
                    self._shadow_note("video_confirm", "wait", close_up(t.pid), RuleId.V1, why)
                elif t.pid not in self._leak_noted:  # once per speaking run
                    self._leak_noted.add(t.pid)
                    self._decide("wait", close_up(t.pid), RuleId.V1, why, blocked_by=RuleId.V1)
            if mode == "on":
                speaking = [t for t in speaking if t not in leaks]
        self._leak_noted &= {t.pid for t in leaks}
        if not speaking:
            return None
        best = max(speaking, key=lambda t: (t.score(self.rules), t.host, -int(t.pid.value[1])))
        shot = close_up(best.pid)
        if self.insert is not None and best.pid == self.insert.speaker:
            return None  # the insert returns to this speaker on its own (H4)
        if self.insert is not None and self.insert.rule is RuleId.B1:
            return None  # B1: the opening and the bird after content are not interrupted
        run = best.run_ms(self._now)
        required, rule, measures = self._required_run_ms(best.pid)
        # H1 evidence asked of a candidate does not drop when the H1 window ends while it waits,
        # so the candidate still gets its time on preview first.
        cand = self.candidate
        if cand is not None and cand.speaker == best.pid and cand.rule is RuleId.H1:
            required = max(required, int(cand.measures.get("required_ms", 0)))
            rule = RuleId.H1
        if shot == self.program:
            if self.insert is not None and run >= required:
                # R3: the listener on screen starts talking; they are now the speaker
                if self.insert.rule is RuleId.R1:
                    self._decide("hold", shot, RuleId.R3, "Lytteren snakker; taler-reglene gjelder")
                self.insert = None
                self.speaker_on_air = best.pid
                self.speaker_on_air_since = self._now
            return None
        arm_at = min(required // 2, max(0, required - PREVIEW_LEAD_MS))
        if run < arm_at:
            return None
        name = self.show.participant(best.pid).name
        measures |= {
            "run_ms": run,
            "required_ms": required,
            "vad": round(best.frame.vad, 2),
            "dominance_db": round(best.frame.dominance_db, 1),
        }
        return Proposal(
            shot,
            rule,
            "speaker",
            f"{name} aktiv {_sec(run)} (krav {_sec(required)})",
            measures,
            confirmed=run >= required,
            speaker=best.pid,
        )

    def _propose_insert_return(self, inp: Inputs) -> Proposal | None:
        ins = self.insert
        if ins is None or self.program == ins.return_to:
            return None
        if self._now < ins.end_ms - RETURN_PREVIEW_MS:
            return None
        on_screen = shots.speaker_of(self.program)
        if on_screen is not None and self.speakers.get(on_screen).speaking:
            return None  # R3: the listener on screen is talking; speaker rules decide
        rule = ins.rule if ins.rule is RuleId.B1 else RuleId.H4
        return Proposal(
            ins.return_to,
            rule,
            "return",
            "Tilbake til taleren" if rule is RuleId.B1 else "Tilbake til samme taler",
            confirmed=self._now >= ins.end_ms,
            speaker=ins.speaker,
        )

    def _propose_variation(self, inp: Inputs) -> Proposal | None:
        """T7 reaction shot / N1 angle change, and B5 short bird's-eye, during long answers."""
        r = self.rules
        speaker = self.speaker_on_air
        if speaker is None or self.insert is not None:
            return None
        talker = self.speakers.get(speaker)
        if shots.speaker_of(self.program) != speaker:
            return None
        if not talker.speaking and talker.frame.pause_ms > VARIATION_PAUSE_MAX_MS:
            return None  # the answer is over; silence rules take it from here
        on_air_ms = self._now - max(self.speaker_on_air_since, self.last_variation_ms)
        if on_air_ms < r.T7_reaction_after_s * 1000:
            return None
        if self.variation_count % 2 == 1 and self._b5_allowed():
            return Proposal(
                BIRD,
                RuleId.B5,
                "insert",
                "Kort fugleperspektiv i langt svar",
                {"on_air_ms": on_air_ms},
                speaker=speaker,
                insert_ms=int(r.B5_min_s * 1000),
            )
        listener = self._listener_for(speaker)
        reacting = self._most_reacting(speaker)
        if reacting is not None and self._mode("reactions") == "on":
            listener = reacting  # V3: the listener who reacts most in the last V3_window_s
        if listener is not None:
            return Proposal(
                close_up(listener),
                RuleId.V3
                if listener == reacting and self._mode("reactions") == "on"
                else RuleId.T7,
                "insert",
                f"Reaksjonsbilde av {self.show.participant(listener).name}",
                {"on_air_ms": on_air_ms},
                speaker=speaker,
                insert_ms=int(r.T7_reaction_shot_s * 1000),
            )
        if self.show.has_wide:  # N1: change angle between CU and WIDE
            return Proposal(
                WIDE,
                RuleId.T7,
                "insert",
                "Vinkelbytte i langt innslag",
                {"on_air_ms": on_air_ms},
                speaker=speaker,
                insert_ms=int(r.T7_reaction_shot_s * 1000),
            )
        return None

    def _b5_allowed(self) -> bool:
        """B5 limits: bird switch on, minimum gap since the last bird, maximum share of time."""
        r = self.rules
        if not shots.available(BIRD, self.show, self.config.features):
            return False
        if self._now - self.last_bird_ms < r.B5_min_gap_s * 1000:
            return False
        elapsed = max(1, self._now - self.origin_ms)
        return self._bird_ms() / elapsed < r.B5_max_share

    def _bird_ms(self) -> int:
        running = self._now - self.program_since if self.program == BIRD else 0
        return self.bird_ms_total + running

    def _listener_for(self, speaker: ParticipantId) -> ParticipantId | None:
        """5.12: a guest talks → show the host; the host talks → the guest who spoke last."""
        others = [p for p in self.show.participants if p.id != speaker]
        if not others:
            return None
        if not self.speakers.get(speaker).host:
            hosts = [p.id for p in others if p.role == "host"]
            if hosts:
                return hosts[0]

        def last_spoke(pid: ParticipantId) -> int:
            t = self.speakers.get(pid)
            return t.last_active if t.last_active is not None else -1

        guests = [p.id for p in others if p.role == "guest"] or [p.id for p in others]
        return max(guests, key=lambda pid: (last_spoke(pid), -int(pid.value[1])))

    def _propose_silence(self, inp: Inputs) -> Proposal | None:
        """T8/B3: nobody talks → the mode's silence shot, after the release time H3."""
        r = self.rules
        silence = self.speakers.silence_ms(self._now)
        # H3: the shot stands at least the release time after the speaker stops
        needed = max(r.T8_silence_s, r.H3_release_s, r.B3_silence_s) * 1000
        release_rule = RuleId.H3
        if self.speakers.speaking() or silence < needed:
            return None
        shot = shots.silence_shot(self.mode, self.show, self.config.features)
        if shot is None:
            return None
        rule = RuleId.B3 if self.config.features.bird and shot in (BIRD, WIDE) else RuleId.T8
        return Proposal(
            shot,
            rule,
            "soft",
            f"Stillhet i {_sec(silence)} (etter release {release_rule.value})",
            {"silence_ms": silence},
        )

    # -- filters (5.7, 5.11) ---------------------------------------------------------------

    def _blocked(self, p: Proposal, inp: Inputs) -> RuleId | None:
        reason = self._eligible(p.shot, inp)
        if reason is not None:
            return reason
        min_shot = (
            int(self.rules.T3_min_shot_s * 1000) if p.timing == "return" else self._min_shot_ms()
        )
        if self._now - self.program_since < min_shot and p.rule is not RuleId.MANUAL:
            return RuleId.T3
        if (
            p.shot == self.previous_program
            and self._now - self.previous_program_end < self.rules.H2_no_return_s * 1000
            and p.timing != "return"
            and p.rule is not RuleId.MANUAL
        ):
            return RuleId.H2
        if not self._cut_allowed():
            return RuleId.S3
        return None

    # -- preview (5.9) ---------------------------------------------------------------------

    def _arm(self, p: Proposal, inp: Inputs) -> None:
        same = self.candidate is not None and self.candidate.shot == p.shot
        self.candidate = p
        self.idle_since = None
        if same:
            if self.preview != p.shot:  # PV1 held it back last time; try again
                self._set_preview(p.shot, p.rule, p.reason, p.measures)
            return
        self.pv_state = PreviewState.ARMED
        self.ready_since = None
        self._set_preview(p.shot, p.rule, p.reason, p.measures)

    def _set_preview(
        self, shot: str, rule: RuleId, reason: str, measures: dict[str, float] | None = None
    ) -> None:
        if shot == self.preview:
            return
        if self._now - self.preview_since < self.rules.PV1_min_preview_s * 1000:
            return  # PV1: no preview flicker; the next tick tries again
        self.preview = shot
        self.preview_since = self._now
        if is_layout(shot):
            self._intent(PrepareLayout(shot))
        elif shot != AUDIO_ONLY:
            self._intent(SetPreview(shots.source_for(shot, self.show)))
        self._decide("preview", shot, rule, reason, measures)

    def _idle(self, inp: Inputs) -> None:
        if self.candidate is not None and self.candidate.timing == "speaker":
            self._decide(
                "wait", self.candidate.shot, self.candidate.rule, "Kandidaten falt bort før kuttet"
            )
        self.candidate = None
        self.ready_since = None
        self.pv_state = PreviewState.IDLE
        self.last_wait = None
        # Preview shows the mode's reserve shot when idle (5.9), unless that is on program.
        if self.idle_since is None:
            self.idle_since = self._now
        if self._now - self.idle_since < IDLE_FALLBACK_MS:
            return
        fallback = shots.fallback_shot(self.mode, self.show, self.config.features)
        if fallback != self.program and self.preview != fallback:
            self._set_preview(fallback, RuleId.PV1, "Reservebilde på preview")

    def _wait(self, p: Proposal, blocked: RuleId) -> None:
        key = (p.shot, blocked)
        if key != self.last_wait:
            self.last_wait = key
            self._decide("wait", p.shot, p.rule, p.reason, p.measures, blocked_by=blocked)

    # -- cut point (5.10) -------------------------------------------------------------------

    def _cut_point(self, p: Proposal) -> bool:
        r = self.rules
        if self.preview != p.shot:
            return False  # preview first (5.9); PV1 may still be holding it back
        current = self.speaker_on_air
        cur = self.speakers.get(current) if current is not None else None
        if p.timing == "speaker":
            if self._ready_ms() < r.K3_max_wait_s * 1000 and (
                self._now - self.preview_since < MIN_PREVIEW_LEAD_MS
            ):
                return False
            if cur is None or cur.frame.pause_ms >= r.K1_pause_ms:
                return self._mark(p, RuleId.K1)
            if cur.frame.pause_ms >= r.K2_pause_ms or (
                cur.frame.pitch_falling and cur.frame.pause_ms >= r.K2_falling_pause_ms
            ):
                return self._mark(p, RuleId.K2)
            if self._ready_ms() >= r.K3_max_wait_s * 1000:
                return self._mark(p, RuleId.K3)
            return False
        if p.timing == "insert":
            if cur is None or cur.frame.pause_ms >= r.K4_pause_ms:
                return self._mark(p, RuleId.K4)
            return False
        if p.timing == "return":
            # K4: back when the speaker starts a new phrase, or straight away if nobody talks
            return cur is None or cur.speaking or not self.speakers.speaking()
        if p.timing == "soft" and cur is not None and cur.speaking:
            # T9: wait briefly for a short pause in the current speaker
            if cur.frame.pause_ms >= T9_PAUSE_MS or self._ready_ms() >= r.T9_max_wait_pause_ms:
                return self._mark(p, RuleId.T9)
            return False
        return True

    def _ready_ms(self) -> int:
        return 0 if self.ready_since is None else self._now - self.ready_since

    def _mark(self, p: Proposal, rule: RuleId) -> bool:
        self._cut_rule = rule
        return True

    # -- taking ---------------------------------------------------------------------------

    def _take(self, p: Proposal) -> None:
        rule = self._cut_rule
        self._cut_rule = None
        measures = dict(p.measures)
        measures["preview_ms"] = self._now - self.preview_since
        transition: Literal["cut", "mix"] = "mix" if is_layout(p.shot) else "cut"
        self._intent(Take(transition))
        if p.rule is RuleId.R1:
            self.last_reaction_ms = self._now  # R2: at most one per R2_min_gap_s
        if p.insert_ms is not None and p.speaker is not None:
            self.insert = Insert(
                p.rule, p.return_to or self.program, p.speaker, self._now + p.insert_ms
            )
            self.variation_count += 1
            self.last_variation_ms = self._now
        else:
            if p.timing == "return":
                self.last_variation_ms = self._now
            self.insert = None
        self._set_program(p.shot)
        self.preview = None
        self.candidate = None
        self.pv_state = PreviewState.IDLE
        self.ready_since = None
        self.last_wait = None
        if p.rule is RuleId.MANUAL:
            self.manual_preview = None
        reason = p.reason if rule is None else f"{p.reason}; kuttpunkt {rule.value}"
        if rule is not None and rule.value.startswith("K"):
            measures["cut_point"] = float(rule.value[1:])
        self._decide("cut", p.shot, p.rule, reason, measures)

    def _take_direct(self, shot: str, rule: RuleId, reason: str, *, force: bool = False) -> None:
        """PV4: overrides and safety go straight to program. S3 still holds unless forced
        by a person (manual cut is the operator's call, I5)."""
        if not force and not self._cut_allowed():
            return
        if shot == AUDIO_ONLY:
            self._intent(ShowAudioOnly())
        else:
            self._intent(DirectCut(shots.source_for(shot, self.show)))
        self._set_program(shot)
        self.candidate = None
        self.insert = None
        self.pv_state = PreviewState.IDLE
        self._decide("cut", shot, rule, f"{reason} (direkte, {RuleId.PV4.value})")

    def _set_program(self, shot: str) -> None:
        if shot != self.program:
            if is_layout(self.program):
                self.layout_ended[self.program] = self._now  # 5.6: no repeat within L_no_repeat_s
            if self._shows_content(self.program):
                self.content.last_on_air_end = self._now
            if self.program == BIRD:
                self.bird_ms_total += self._now - self.program_since
                self.last_bird_ms = self._now
            self.previous_program = self.program
            self.previous_program_end = self._now
            self.program = shot
            self.program_since = self._now
            self.last_cut_ms = self._now
            self.settle_until = self._now + SETTLE_MS
        if self.insert is not None:
            return  # during a reaction or bird insert the speaker on air does not change (H4)
        speaker = shots.speaker_of(shot)
        if speaker is None:
            self.speaker_on_air = None
        elif speaker != self.speaker_on_air:
            self.speaker_on_air = speaker
            self.speaker_on_air_since = self._now
            self.last_variation_ms = self._now

    def _audio_only(self) -> None:
        if self.program != AUDIO_ONLY:
            self._take_direct(AUDIO_ONLY, RuleId.MANUAL, "Kun lyd: fast grafikk", force=True)

    # -- output ---------------------------------------------------------------------------

    def _companion_variables(self) -> None:
        values = {
            "regi_shot": self.program,
            "regi_mode": self.mode.value,
            "regi_auto": "off" if self.paused else "on",
        }
        for name, value in values.items():
            if self.vars.get(name) != value:
                self.vars[name] = value
                self._intent(SetCompanionVariable(name, value))

    # -- the picture rules (6.5: V1–V5, PV3) and reactions (R1–R3) -------------------------

    def _observe(self, inp: Inputs) -> None:
        """Keep what the video layer saw: mouths, reactions and still pictures."""
        v, now = inp.vision, self._now
        if v is None:
            self._still_since.clear()
            return
        window = int(self.rules.V3_window_s * 1000)
        for p in self.show.participants:
            tile = v.get(SourceId(p.camera.value))
            if tile is None:
                continue
            if tile.mouth >= MOUTH_ON:
                self._mouth_at[p.id] = now
            hist = self._reacts.setdefault(p.id, deque())
            hist.append((now, max(tile.smile, tile.nod)))
            while hist and now - hist[0][0] > window:
                hist.popleft()
        for src, tile in v.items():
            if tile.moving or not tile.face_ok:
                self._still_since.pop(src, None)
            else:
                self._still_since.setdefault(src, now)

    def _vision_on(self) -> bool:
        return self._mode("video_confirm") != "off"

    def _mouth_moves(self, pid: ParticipantId) -> bool:
        at = self._mouth_at.get(pid)
        recent = MOUTH_RECENT_MS + self.config.vision_delay_ms
        return self._vision_on() and at is not None and self._now - at <= recent

    def _mouth_still(self, pid: ParticipantId, since: int | None) -> bool:
        """V1 leakage: the mic has been active for V1_leak_ms and the mouth has not moved.

        The picture lags the sound by ``vision_delay_ms`` (D-071): a mouth seen at ``at`` moved
        at ``at - delay``, and the mouth gets that much longer to show up."""
        if not self._vision_on() or since is None or not self._still_since:
            return False
        delay = self.config.vision_delay_ms
        if self._now - since < self.rules.V1_leak_ms + delay:
            return False
        at = self._mouth_at.get(pid)
        return at is None or at - delay < since

    def _pv3(self, p: Proposal, inp: Inputs) -> RuleId | None:
        """PV3: with video, the preview window must show a valid, still face before TAKE."""
        if self._mode("video_confirm") != "on" or inp.vision is None:
            return None
        cam = shots.camera_of(p.shot, self.show)
        if cam is None or shots.speaker_of(p.shot) is None:
            return None
        src = SourceId(cam.value)
        tile = inp.vision.get(src)
        if tile is None:
            return None
        if not tile.face_ok:
            return RuleId.V2  # no valid face in the window
        since = self._still_since.get(src)
        if since is None or self._now - since < self.rules.V5_still_s * 1000:
            return RuleId.PV3
        return None

    def _reaction(self, pid: ParticipantId) -> float:
        hist = self._reacts.get(pid)
        score = max((s for _, s in hist), default=0.0) if hist else 0.0
        if self.speakers.get(pid).laughing:
            score = 1.0  # the listener's own mic hears the laugh (R1)
        return score

    def _most_reacting(self, speaker: ParticipantId) -> ParticipantId | None:
        """V3: the listener with the strongest smile, nod or laugh in the last V3_window_s."""
        others = [p.id for p in self.show.participants if p.id != speaker]
        if not others or not self._reacts:
            return None
        best = max(others, key=self._reaction)
        return best if self._reaction(best) >= self.rules.R1_react_min else None

    def _propose_reaction(self, inp: Inputs) -> Proposal | None:
        """R1: a listener nods, smiles or laughs while the speaker has talked a while →
        a reaction shot in the speaker's next pause (K4). R2: at most one per R2_min_gap_s,
        never on answers shorter than R1_speaker_min_s."""
        mode = self._mode("reactions")
        if mode == "off" or inp.vision is None:
            return None
        r, now = self.rules, self._now
        speaker = self.speaker_on_air
        if speaker is None or self.insert is not None:
            return None
        if shots.speaker_of(self.program) != speaker:
            return None
        listener = self._most_reacting(speaker)
        if listener is None:
            self._r2_noted = None
            return None
        short = now - self.speaker_on_air_since < r.R1_speaker_min_s * 1000
        if short or now - self.last_reaction_ms < r.R2_min_gap_s * 1000:
            if self._r2_noted != listener:  # R2: never on short answers, at most one per gap
                self._r2_noted = listener
                why = "Kort svar" if short else "For kort tid siden forrige reaksjon"
                self._decide("wait", close_up(listener), RuleId.R1, why, blocked_by=RuleId.R2)
            return None
        name = self.show.participant(listener).name
        p = Proposal(
            close_up(listener),
            RuleId.R1,
            "insert",
            f"Reaksjon fra {name}",
            {"reaction": round(self._reaction(listener), 2)},
            speaker=speaker,
            insert_ms=int(r.R1_shot_s * 1000),
        )
        if mode == "shadow":
            self._shadow_note("reactions", "preview", p.shot, p.rule, p.reason, p.measures)
            return None
        return p

    def _correct_framing(self, inp: Inputs, on_air: set[CameraId]) -> None:
        """V4: a face that sits wrong in an off-air close-up is corrected with small steps,
        at most every 2 s; never on the candidate, a tracking camera or one being reframed."""
        if self._mode("video_confirm") != "on" or inp.vision is None:
            return
        cand = self.candidate
        cand_cam = shots.camera_of(cand.shot, self.show) if cand is not None else None
        for p in self.show.participants:
            cam = p.camera
            cfg = self.show.cameras.get(cam)
            tile = inp.vision.get(SourceId(cam.value))
            if (
                cfg is None
                or cfg.driver == "none"
                or cam in on_air
                or cam == cand_cam
                or cam in inp.cameras_tracking
                or cam in inp.cameras_moving
                or self._now < self.reframe_until.get(cam, -1)
                or tile is None
                or tile.face_x is None
                or tile.face_y is None
                or self._now - self._v4_at.get(cam, -(10**9)) < V4_EVERY_MS
            ):
                continue
            dx, dy = tile.face_x - V4_TARGET_X, tile.face_y - V4_TARGET_Y
            err = self.rules.V4_error
            pan = V4_STEP if dx > err else -V4_STEP if dx < -err else 0.0
            tilt = -V4_STEP if dy > err else V4_STEP if dy < -err else 0.0
            if pan or tilt:
                self._v4_at[cam] = self._now
                self._intent(NudgeCamera(cam, pan, tilt))
                self._decide(
                    "hold",
                    close_up(p.id),
                    RuleId.V4,
                    f"{cam.value}: utsnittet rettes (ansikt {tile.face_x:.2f}, {tile.face_y:.2f})",
                )

    # -- framing variety (F1–F3) and slow zoom (Z1–Z3), spec 5.13 ----------------------------

    def _cameras_on_air(self) -> set[CameraId]:
        out: set[CameraId] = set()
        for shot in (self.program, self.preview):
            if shot is None or shot == AUDIO_ONLY:
                continue
            if is_layout(shot):
                out |= {self.show.participant(p).camera for p in shot_participants(shot)}
                continue
            cam = shots.camera_of(shot, self.show)
            if cam is not None:
                out.add(cam)
        return out

    def _cameras(self, inp: Inputs) -> None:
        on_air = self._cameras_on_air()
        self._reframe_pending |= self._on_air_before - on_air  # F1: just went off air
        self._on_air_before = on_air
        for name, fn in (
            ("framing_variety", self._reframe),
            ("slow_zoom", self._slow_zoom),
            ("video_confirm", self._correct_framing),
        ):
            try:
                fn(inp, on_air)
            except Exception as exc:  # a switch never stops base mode (F-1)
                self._switch_failed(name, exc)

    def _close_up_of(self, cam: CameraId) -> str | None:
        p = next((p for p in self.show.participants if p.camera == cam), None)
        return close_up(p.id) if p is not None else None

    def _reframe(self, inp: Inputs, on_air: set[CameraId]) -> None:
        """F1: a camera that went off program and preview gets the other framing (tight or
        wide), so the same person does not get the same framing twice in a row. F3: never the
        camera that is the candidate for the next cut. A camera that was slowly zoomed in goes
        back to its framing even with F off."""
        mode = self._mode("framing_variety")
        zoom_on = self._mode("slow_zoom") == "on"
        for cam in sorted(self._reframe_pending):
            cfg = self.show.cameras.get(cam)
            shot = self._close_up_of(cam)
            usable = (
                cfg is not None
                and cfg.driver != "none"
                and cfg.role == "closeup"
                and {"tight", "wide"} <= set(cfg.presets)
                and shot is not None
            )
            if not usable or shot is None or cam in on_air:
                self._reframe_pending.discard(cam)
                continue
            if cam in inp.cameras_tracking:
                self._reframe_pending.discard(cam)  # AT3: the camera follows the person
                self._decide("hold", shot, RuleId.AT3, f"{cam.value} følger personen selv")
                continue
            cand = self.candidate
            if cand is not None and shots.camera_of(cand.shot, self.show) == cam:
                if cam not in self._f3_waiting:  # F3: wait until it is no longer the candidate
                    self._f3_waiting.add(cam)
                    self._decide("wait", shot, RuleId.F3, f"{cam.value} er neste kandidat")
                continue
            self._f3_waiting.discard(cam)
            if cam in inp.cameras_moving:
                continue
            now_framing = self.framing.get(cam, "tight")
            zoomed = cam in self._zoomed
            self._reframe_pending.discard(cam)
            self._zoomed.discard(cam)
            if mode == "off":
                if zoomed and zoom_on:
                    self._send_frame(cam, now_framing, shot, RuleId.Z2, "zoomet ut igjen")
                continue
            nxt = "wide" if now_framing == "tight" else "tight"
            word = "videre" if nxt == "wide" else "tett"
            if mode == "shadow":
                self._shadow_note(
                    "framing_variety", "hold", shot, RuleId.F1, f"Ville gitt {word} utsnitt"
                )
                if zoomed and zoom_on:
                    self._send_frame(cam, now_framing, shot, RuleId.Z2, "zoomet ut igjen")
                continue
            self._send_frame(cam, nxt, shot, RuleId.F1, f"{word} utsnitt mens det er av lufta")

    def _send_frame(self, cam: CameraId, framing: str, shot: str, rule: RuleId, why: str) -> None:
        self.framing[cam] = framing
        self.reframe_until[cam] = self._now + int(
            (self.rules.F_reframe_grace_s + self.rules.F2_settle_s) * 1000
        )
        self._intent(FrameCamera(cam, "wide" if framing == "wide" else "tight"))
        self._decide("hold", shot, rule, f"{cam.value}: {why}")

    def _slow_zoom(self, inp: Inputs, on_air: set[CameraId]) -> None:
        """Z1: the same speaker has stood a while → zoom in a little over a long time, on the
        camera on air. Z2: stops at once when another shot is armed on preview or the shot
        changes. Z3: only cameras with ``slow_zoom`` in the show."""
        r, now = self.rules, self._now
        if self._zoom is not None:
            shot, cam, start = self._zoom
            ended = now - start >= r.Z1_duration_s * 1000
            armed = self.candidate is not None and self.candidate.shot != shot
            if self.program != shot or armed:
                self._intent(StopZoom(cam))
                self._decide("hold", shot, RuleId.Z2, f"{cam.value}: langsom zoom stoppet")
                self._zoom = None
            elif ended:
                self._zoom = None
            return
        mode = self._mode("slow_zoom")
        if mode == "off":
            return
        pid = shots.speaker_of(self.program)
        if pid is None or self.candidate is not None:
            return
        cam = self.show.participant(pid).camera
        cfg = self.show.cameras.get(cam)
        if cfg is None or not cfg.slow_zoom or cfg.driver == "none" or cam in self._zoomed:
            return
        if cam in inp.cameras_tracking:
            return  # AT3: no slow zoom while the camera tracks
        talker = self.speakers.get(pid)
        if not talker.speaking or now - self.program_since < r.Z1_after_s * 1000:
            return
        why = f"{cam.value}: langsom zoom inn {r.Z1_max_zoom:.0%} over {r.Z1_duration_s:g} s"
        if mode == "shadow":
            self._shadow_note("slow_zoom", "hold", self.program, RuleId.Z1, why)
            return
        self._intent(SlowZoom(cam, r.Z1_max_zoom, int(r.Z1_duration_s * 1000)))
        self._decide("hold", self.program, RuleId.Z1, why)
        self._zoom = (self.program, cam, now)
        self._zoomed.add(cam)

    # -- switches (spec 5.13, F-1) ------------------------------------------------------------

    def _mode(self, name: str) -> FeatureMode:
        """``off``, ``shadow`` or ``on``. A switch whose rules failed counts as off until the
        studio has moved it to shadow (``failed_switches``)."""
        if name in self.failed_switches:
            return "off"
        return self.config.features.mode(name)

    def _shadow_note(
        self,
        switch: str,
        action: DecisionAction,
        shot: str,
        rule: RuleId,
        reason: str,
        measures: dict[str, float] | None = None,
    ) -> None:
        """What a switch in shadow would have done: logged, never acted on. The same note is
        logged again only after ``SHADOW_REPEAT_MS``, so the log does not fill every tick."""
        key = (switch, action, shot, rule)
        last = self._shadow_seen.get(key)
        if last is not None and self._now - last < SHADOW_REPEAT_MS:
            return
        self._shadow_seen[key] = self._now
        self._decide(action, shot, rule, reason, measures, switch=switch)

    def _switch_failed(self, switch: str, exc: Exception) -> None:
        """A switch's rules raised: base mode carries on without it (5.13)."""
        if switch not in self.failed_switches:
            self.failed_switches.add(switch)
            self._decide(
                "hold",
                self.program,
                RuleId.S2,
                f"Bryteren {switch} feilet ({type(exc).__name__}); grunnmodus fortsetter",
                switch=switch,
            )

    def _intent(self, intent: Intent) -> None:
        if not self.shadow:
            self._intents.append(intent)

    def _decide(
        self,
        action: DecisionAction,
        shot: str,
        rule: RuleId,
        reason: str,
        measures: dict[str, float] | None = None,
        blocked_by: RuleId | None = None,
        switch: str | None = None,
    ) -> None:
        self._seq += 1
        self._decisions.append(
            Decision(
                ts=self.wall_origin + timedelta(milliseconds=self._now - self.origin_ms),
                mono_ms=max(0, self._now),
                mode=self.mode,
                action=action,
                shot=shot,
                rule=rule,
                reason=reason,
                measures=dict(measures or {}),
                blocked_by=blocked_by,
                correlation_id=f"d-{self._seq}",
                shadow=self.shadow or switch is not None,
                switch=switch,
            )
        )
        if action == "cut" and not self.shadow and switch is None:
            for name, value in (("regi_rule", rule.value), ("regi_reason", reason)):
                if self.vars.get(name) != value:
                    self.vars[name] = value
                    self._intents.append(SetCompanionVariable(name, value))
