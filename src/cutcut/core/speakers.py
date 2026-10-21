"""Who is talking (spec 5.3, 5.7 S6, 5.12): T1, T5, T6, T12 bookkeeping per participant.

Pure and deterministic: everything is driven by ``now_ms`` and the mic frames.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from cutcut.common.config.rules import RuleParams
from cutcut.common.ids import MicId, ParticipantId, RuleId
from cutcut.common.models.show import ShowConfig
from cutcut.core.inputs import SILENT, MicFrame

# Rule IDs this module implements (spec 12.1: every rule ID exists as a constant in code).
IMPLEMENTS = (RuleId.T1, RuleId.T12, RuleId.S6, RuleId.T6)

# Gaps shorter than this inside speech (breaths, plosives) do not end a speaking run.
# Kept below K2/K4 pauses so a real phrase pause is still visible to the cut-point rules.
HANGOVER_MS = 200


@dataclass
class Talker:
    pid: ParticipantId
    mic: MicId
    host: bool
    speaking: bool = False
    speaking_since: int | None = None
    last_active: int | None = None
    silent_since: int | None = 0
    muted: bool = False  # S6: active on the mic but missing in the main mix
    laughing: bool = False
    frame: MicFrame = SILENT

    def run_ms(self, now: int) -> int:
        if not self.speaking or self.speaking_since is None:
            return 0
        return now - self.speaking_since

    def score(self, rules: RuleParams) -> float:
        """Linear dominance with the host weight (T12)."""
        weight = rules.T12_host_weight if self.host else 1.0
        return math.pow(10, self.frame.dominance_db / 20) * weight


@dataclass
class Speakers:
    talkers: dict[ParticipantId, Talker]
    crosstalk_since: int | None = None
    laughter_since: int | None = None
    all_silent_since: int | None = 0
    dominant: ParticipantId | None = None
    turns: deque[int] = field(default_factory=deque)  # times of dominant-speaker changes (T6)
    _last_turn_from: ParticipantId | None = None

    @classmethod
    def for_show(cls, show: ShowConfig) -> Speakers:
        return cls(
            talkers={
                p.id: Talker(pid=p.id, mic=p.mic, host=p.role == "host") for p in show.participants
            }
        )

    # -- per tick ---------------------------------------------------------------------------

    def update(self, now: int, mics: dict[MicId, MicFrame], rules: RuleParams) -> None:
        for t in self.talkers.values():
            frame = mics.get(t.mic, SILENT)
            t.frame = frame
            voiced = frame.vad >= rules.T1_vad_threshold and not frame.leak
            t.muted = voiced and not frame.in_main_mix
            # T1: active = VAD over threshold and dominant over leakage; S6: muted never counts
            raw = voiced and frame.dominance_db >= rules.T1_dominance_db and not t.muted
            t.laughing = frame.laughter and frame.in_main_mix
            if raw:
                t.last_active = now
                if not t.speaking:
                    t.speaking = True
                    t.speaking_since = now
                    t.silent_since = None
            elif t.speaking and t.last_active is not None and now - t.last_active > HANGOVER_MS:
                t.speaking = False
                t.speaking_since = None
                t.silent_since = t.last_active

        speaking = self.speaking()
        if len(speaking) >= 2:
            self.crosstalk_since = self.crosstalk_since if self.crosstalk_since is not None else now
        else:
            self.crosstalk_since = None
        laughing = [t for t in self.talkers.values() if t.laughing]
        if len(laughing) >= 2:
            self.laughter_since = self.laughter_since if self.laughter_since is not None else now
        else:
            self.laughter_since = None
        if speaking:
            self.all_silent_since = None
        elif self.all_silent_since is None:
            self.all_silent_since = max(
                (t.silent_since for t in self.talkers.values() if t.silent_since is not None),
                default=now,
            )

        self._update_dominant(now, rules)

    def _update_dominant(self, now: int, rules: RuleParams) -> None:
        speaking = self.speaking()
        if not speaking:
            return  # keep the last dominant speaker through silence
        best = max(speaking, key=lambda t: (t.score(rules), t.host, -int(t.pid.value[1])))
        if best.pid != self.dominant and best.run_ms(now) >= rules.T2_confirm_ms:
            if self.dominant is not None:
                self.turns.append(now)  # T6 counts confirmed changes of who holds the floor
            self.dominant = best.pid
        window = int(rules.T6_window_s * 1000)
        while self.turns and now - self.turns[0] > window:
            self.turns.popleft()

    # -- queries ----------------------------------------------------------------------------

    def speaking(self) -> list[Talker]:
        return [t for t in self.talkers.values() if t.speaking]

    def get(self, pid: ParticipantId) -> Talker:
        return self.talkers[pid]

    def crosstalk_ms(self, now: int) -> int:
        return 0 if self.crosstalk_since is None else now - self.crosstalk_since

    def laughter_ms(self, now: int) -> int:
        return 0 if self.laughter_since is None else now - self.laughter_since

    def silence_ms(self, now: int) -> int:
        return 0 if self.all_silent_since is None else now - self.all_silent_since

    def pingpong(self, rules: RuleParams) -> bool:
        return len(self.turns) >= rules.T6_pingpong_switches
