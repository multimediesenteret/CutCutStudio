"""Synthetic talkers that produce the same ``MicFrame`` measurements as ``audio-capture``.

Two ways to drive them:

* **Script:** explicit "P2 talks from 12 s for 25 s" segments (scenarios, tests).
* **Conversation:** a seeded stochastic model of turn-taking with phrases and pauses,
  overlaps, back-channels ("mm"), laughter and leakage between mics. Same seed, same talk.

No audio is generated – only the per-mic measurements the engine uses (PL-02).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from cutcut.common.ids import MicId, ParticipantId
from cutcut.common.models.show import ShowConfig
from cutcut.core.inputs import MicFrame


@dataclass
class VoiceState:
    talking: bool = False
    stopped_at: int = -(10**9)
    pitch_falling: bool = False
    dominance_db: float = 12.0
    vad: float = 0.9
    muted: bool = False  # muted on the mixer: still on the pre-fader track (S6)
    laughing_until: int = -1


@dataclass
class Voices:
    """Mic measurements for the participants (M1–M4) and the laptop (M5)."""

    show: ShowConfig
    seed: int = 1
    voices: dict[ParticipantId, VoiceState] = field(default_factory=dict)
    laptop: VoiceState = field(default_factory=VoiceState)
    leak_db: float = 3.0  # how far above its own floor a neighbour's voice shows up

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)  # noqa: S311 - simulation, not security
        self.voices = {p.id: VoiceState() for p in self.show.participants}

    # -- direct control -------------------------------------------------------------------

    def talk(self, pid: ParticipantId, now: int, dominance_db: float = 12.0) -> None:
        v = self.voices[pid]
        v.talking, v.dominance_db = True, dominance_db

    def stop(self, pid: ParticipantId, now: int, pitch_falling: bool = True) -> None:
        v = self.voices[pid]
        if v.talking:
            v.stopped_at = now
        v.talking, v.pitch_falling = False, pitch_falling

    def laugh(self, pid: ParticipantId, now: int, ms: int) -> None:
        self.voices[pid].laughing_until = now + ms

    # -- measurements ---------------------------------------------------------------------

    def frames(self, now: int) -> dict[MicId, MicFrame]:
        out: dict[MicId, MicFrame] = {}
        anyone = any(v.talking for v in self.voices.values())
        for p in self.show.participants:
            out[p.mic] = self._frame(self.voices[p.id], now, anyone)
        out[MicId.M5] = self._frame(self.laptop, now, False)
        return out

    def _frame(self, v: VoiceState, now: int, someone_else_talks: bool) -> MicFrame:
        laughing = now < v.laughing_until
        jitter = self.rng.uniform(-0.05, 0.05)
        if v.talking:
            return MicFrame(
                vad=min(1.0, v.vad + jitter),
                level_db=-20 + jitter * 20,
                dominance_db=v.dominance_db + jitter * 20,
                pause_ms=0,
                in_main_mix=not v.muted,
                laughter=laughing,
            )
        pause = max(0, min(now - v.stopped_at, 60_000))
        if someone_else_talks:  # leakage: the neighbour is heard faintly on this mic
            return MicFrame(
                vad=0.55 + jitter,
                level_db=-38,
                dominance_db=self.leak_db,
                pause_ms=pause,
                phrase_end=True,
                pitch_falling=v.pitch_falling,
                in_main_mix=not v.muted,
                leak=True,
                laughter=laughing,
            )
        return MicFrame(
            vad=max(0.0, 0.04 + jitter / 2),
            level_db=-60,
            dominance_db=0.0,
            pause_ms=pause,
            phrase_end=True,
            pitch_falling=v.pitch_falling,
            in_main_mix=not v.muted,
            laughter=laughing,
        )


@dataclass
class Conversation:
    """Seeded turn-taking: who talks next, phrase lengths, pauses, overlaps, back-channels."""

    voices: Voices
    seed: int = 1
    mean_turn_s: float = 12.0
    overlap_prob: float = 0.15
    backchannel_prob: float = 0.25
    laughter_prob: float = 0.03
    speaker: ParticipantId | None = None
    turn_end: int = 0
    phrase_end: int = 0
    pause_end: int = 0
    _backchannel: tuple[ParticipantId, int] | None = None

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed * 7919)  # noqa: S311 - simulation
        self.ids = [p.id for p in self.voices.show.participants]
        self.hosts = [p.id for p in self.voices.show.participants if p.role == "host"]

    def _next_speaker(self) -> ParticipantId:
        others = [p for p in self.ids if p != self.speaker] or self.ids
        guest_spoke = self.speaker is not None and self.speaker not in self.hosts and self.hosts
        if guest_spoke and self.rng.random() < 0.6:
            return self.rng.choice(self.hosts)  # answers usually go back to the host
        return self.rng.choice(others)

    def update(self, now: int) -> None:
        v = self.voices
        if self.speaker is None or now >= self.turn_end:
            prev = self.speaker
            self.speaker = self._next_speaker()
            turn_ms = int(self.rng.lognormvariate(0, 0.6) * self.mean_turn_s * 1000)
            self.turn_end = now + max(1500, turn_ms)
            overlap = prev is not None and self.rng.random() < self.overlap_prob
            if prev is not None and not overlap:
                v.stop(prev, now, pitch_falling=True)
            if overlap and prev is not None:
                self._backchannel = (prev, now + self.rng.randint(200, 700))
            v.talk(self.speaker, now, dominance_db=self.rng.uniform(9, 16))
            self.phrase_end = now + self.rng.randint(1500, 5000)
            self.pause_end = 0
            if self.rng.random() < self.laughter_prob and len(self.ids) >= 2:
                for pid in self.rng.sample(self.ids, 2):
                    v.laugh(pid, now, self.rng.randint(1500, 3500))
        if self.pause_end and now >= self.pause_end:
            v.talk(self.speaker, now, dominance_db=v.voices[self.speaker].dominance_db)
            self.phrase_end = now + self.rng.randint(1500, 5000)
            self.pause_end = 0
        elif not self.pause_end and now >= self.phrase_end:
            v.stop(self.speaker, now, pitch_falling=self.rng.random() < 0.7)
            self.pause_end = now + self.rng.randint(200, 900)
        # back-channels and overlap tails from listeners
        if self._backchannel is not None and now >= self._backchannel[1]:
            v.stop(self._backchannel[0], now, pitch_falling=True)
            self._backchannel = None
        elif self._backchannel is None and self.rng.random() < self.backchannel_prob / 300:
            listeners = [p for p in self.ids if p != self.speaker]
            if listeners:
                who = self.rng.choice(listeners)
                v.talk(who, now, dominance_db=self.rng.uniform(6, 10))
                self._backchannel = (who, now + self.rng.randint(300, 800))
