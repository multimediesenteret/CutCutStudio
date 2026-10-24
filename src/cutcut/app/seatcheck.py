"""P12 Plassjekk: does each person sit in front of their own camera?

Each mic belongs to one seat and one camera (mic 2 → camera 2). If guest 1 sits in front of
camera 3, CutCut cuts confidently to the wrong person for the whole session, and in a studio
without a technician no one sees it. This compares who is talking with which picture shows a
moving mouth, from what is measured anyway: ``active``/``leak`` per mic from audio-capture,
and ``mouth``/``face_ok`` per camera window from the video layer (P6).

Only moments when exactly one person talks are used (clean measurements). After at least
``MIN_SOLO_MS`` of a person talking alone, their row is judged:

* **wrong seat:** another camera shows a moving mouth at least ``WRONG_SHARE`` of the time,
  and ``MARGIN`` more than their own camera;
* **swap:** two people each point at the other's camera;
* **empty:** their own camera shows no face ``EMPTY_FACE`` or more of the time.

Pure: no clock, no I/O. The studio feeds it every tick during the countdown and the first
``RUN_MS`` of the recording, and decides what to show (shadow: log only).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from cutcut.common.ids import CameraId, MicId, ParticipantId, SourceId
from cutcut.core.inputs import MicFrame, TileFrame

MIN_SOLO_MS: Final = 15_000
RUN_MS: Final = 120_000  # how long into the recording the check runs
MOUTH_ON: Final = 0.3  # as the engine's V1
WRONG_SHARE: Final = 0.5
MARGIN: Final = 0.25
EMPTY_FACE: Final = 0.2  # own camera shows a face less than this share of the time → empty
VOICED_DB: Final = -50.0
SOLO_DOMINANCE_DB: Final = 10.0
CLOSE_UPS: Final = (CameraId.C1, CameraId.C2, CameraId.C3, CameraId.C4)

Kind = Literal["wrong", "swap", "empty"]


@dataclass(frozen=True)
class Seat:
    mic: MicId
    camera: CameraId


@dataclass(frozen=True)
class SeatFinding:
    pid: ParticipantId
    kind: Kind
    expected: CameraId
    seen: CameraId | None = None  # where their mouth moved (wrong, swap)
    other: ParticipantId | None = None  # who they swapped with
    share: float = 0.0  # how much of their speech the seen camera showed a moving mouth


@dataclass
class SeatCheck:
    seats: dict[ParticipantId, Seat]
    solo_ms: dict[ParticipantId, int] = field(default_factory=dict)
    mouth_ms: dict[ParticipantId, dict[CameraId, int]] = field(default_factory=dict)
    face_ms: dict[ParticipantId, int] = field(default_factory=dict)

    def feed(
        self,
        dt_ms: int,
        mics: Mapping[MicId, MicFrame],
        tiles: Mapping[SourceId, TileFrame] | None,
    ) -> None:
        if tiles is None or dt_ms <= 0:
            return
        talking = [pid for pid, seat in self.seats.items() if _voiced(mics.get(seat.mic))]
        if len(talking) != 1:
            return
        pid = talking[0]
        frame = mics[self.seats[pid].mic]
        if frame.dominance_db < SOLO_DOMINANCE_DB:
            return
        self.solo_ms[pid] = self.solo_ms.get(pid, 0) + dt_ms
        row = self.mouth_ms.setdefault(pid, {})
        for cam in CLOSE_UPS:
            tile = tiles.get(SourceId(cam.value))
            if tile is not None and tile.face_ok and tile.mouth >= MOUTH_ON:
                row[cam] = row.get(cam, 0) + dt_ms
        own = tiles.get(SourceId(self.seats[pid].camera.value))
        if own is not None and own.face_ok:
            self.face_ms[pid] = self.face_ms.get(pid, 0) + dt_ms

    def ready(self, pid: ParticipantId) -> bool:
        return self.solo_ms.get(pid, 0) >= MIN_SOLO_MS

    def done(self) -> bool:
        return all(self.ready(pid) for pid in self.seats)

    def shares(self, pid: ParticipantId) -> dict[CameraId, float]:
        solo = self.solo_ms.get(pid, 0)
        if solo <= 0:
            return {}
        return {cam: ms / solo for cam, ms in self.mouth_ms.get(pid, {}).items()}

    def findings(self) -> list[SeatFinding]:
        """What can be said now, for the people with enough speech alone."""
        out: dict[ParticipantId, SeatFinding] = {}
        for pid, seat in self.seats.items():
            if not self.ready(pid):
                continue
            share = self.shares(pid)
            own = share.get(seat.camera, 0.0)
            best = max(share, key=lambda c: share[c], default=None)
            if (
                best is not None
                and best != seat.camera
                and share[best] >= WRONG_SHARE
                and share[best] - own >= MARGIN
            ):
                out[pid] = SeatFinding(pid, "wrong", seat.camera, best, share=round(share[best], 2))
            elif self.face_ms.get(pid, 0) / self.solo_ms[pid] < EMPTY_FACE:
                out[pid] = SeatFinding(pid, "empty", seat.camera)
        by_camera = {s.camera: q for q, s in self.seats.items()}
        pairs = []
        for pid, f in out.items():
            other = by_camera.get(f.seen) if f.kind == "wrong" and f.seen else None
            g = out.get(other) if other is not None else None
            if other is not None and g is not None and g.kind == "wrong" and g.seen == f.expected:
                pairs.append((pid, other))
        for pid, other in pairs:
            f = out[pid]
            out[pid] = SeatFinding(pid, "swap", f.expected, f.seen, other, f.share)
        return [out[pid] for pid in self.seats if pid in out]


def _voiced(f: MicFrame | None) -> bool:
    return f is not None and f.vad >= 0.5 and f.level_db > VOICED_DB and not f.leak


def swapped(
    seats: Mapping[ParticipantId, Seat], finding: SeatFinding
) -> dict[ParticipantId, CameraId]:
    """The cameras «Bytt i CutCut» gives for this session: the person gets the camera their
    mouth was seen on, and whoever had that camera gets theirs."""
    if finding.seen is None:
        return {}
    out = {finding.pid: finding.seen}
    for pid, seat in seats.items():
        if pid != finding.pid and seat.camera == finding.seen:
            out[pid] = finding.expected
    return out
