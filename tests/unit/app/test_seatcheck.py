"""P12: the seat check compares who talks with which camera shows a moving mouth."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cutcut.app.seatcheck import MIN_SOLO_MS, Seat, SeatCheck, swapped
from cutcut.common.ids import CameraId, MicId, ParticipantId, SourceId
from cutcut.core.inputs import MicFrame, TileFrame
from cutcut.core.runtime import TICK_MS
from tests.unit.api.test_api import Rig

P1, P2, P3 = ParticipantId("P1"), ParticipantId("P2"), ParticipantId("P3")
SEATS = {
    P1: Seat(MicId.M1, CameraId.C1),
    P2: Seat(MicId.M2, CameraId.C2),
    P3: Seat(MicId.M3, CameraId.C3),
}
ON = MicFrame(vad=0.9, level_db=-20, dominance_db=15)
OFF = MicFrame(vad=0.05, level_db=-60, dominance_db=-15)


def mics(talker: ParticipantId | None, *, leak: bool = False) -> dict[MicId, MicFrame]:
    out = {s.mic: OFF for s in SEATS.values()}
    if talker is not None:
        frame = MicFrame(vad=0.9, level_db=-20, dominance_db=15, leak=leak)
        out[SEATS[talker].mic] = frame
    return out


def tiles(
    mouth_on: CameraId | None, faces: set[CameraId] | None = None
) -> dict[SourceId, TileFrame]:
    faces = faces if faces is not None else {CameraId.C1, CameraId.C2, CameraId.C3}
    return {
        SourceId(c.value): TileFrame(face_ok=c in faces, mouth=0.8 if c == mouth_on else 0.0)
        for c in (CameraId.C1, CameraId.C2, CameraId.C3, CameraId.C4)
    }


def talk(
    check: SeatCheck, who: ParticipantId, seen: CameraId | None, ms: int = MIN_SOLO_MS, **kw: object
) -> None:
    for _ in range(ms // 100):
        check.feed(100, mics(who), tiles(seen, **kw))  # type: ignore[arg-type]


def test_everyone_in_their_seat_gives_nothing() -> None:
    c = SeatCheck(dict(SEATS))
    for p in (P1, P2, P3):
        talk(c, p, SEATS[p].camera)
    assert c.done()
    assert c.findings() == []


def test_a_guest_at_the_wrong_camera() -> None:
    c = SeatCheck(dict(SEATS))
    talk(c, P2, CameraId.C3)
    (f,) = c.findings()
    assert (f.pid, f.kind, f.expected, f.seen) == (P2, "wrong", CameraId.C2, CameraId.C3)
    assert swapped(SEATS, f) == {P2: CameraId.C3, P3: CameraId.C2}


def test_two_people_who_swapped_seats() -> None:
    c = SeatCheck(dict(SEATS))
    talk(c, P2, CameraId.C3)
    talk(c, P3, CameraId.C2)
    kinds = {f.pid: (f.kind, f.other) for f in c.findings()}
    assert kinds == {P2: ("swap", P3), P3: ("swap", P2)}


def test_an_empty_seat() -> None:
    c = SeatCheck(dict(SEATS))
    talk(c, P1, None, faces={CameraId.C2, CameraId.C3})
    (f,) = c.findings()
    assert (f.kind, f.expected) == ("empty", CameraId.C1)


def test_too_little_speech_says_nothing_yet() -> None:
    c = SeatCheck(dict(SEATS))
    talk(c, P2, CameraId.C3, ms=MIN_SOLO_MS - 1000)
    assert c.findings() == []


def test_only_one_person_talking_counts() -> None:
    c = SeatCheck(dict(SEATS))
    both = {**mics(P2), SEATS[P3].mic: ON}
    for _ in range(300):
        c.feed(100, both, tiles(CameraId.C3))
    assert c.solo_ms == {}
    for _ in range(300):  # leakage is not talking
        c.feed(100, mics(P2, leak=True), tiles(CameraId.C3))
    assert c.solo_ms == {}


def test_no_video_layer_no_check() -> None:
    c = SeatCheck(dict(SEATS))
    for _ in range(300):
        c.feed(100, mics(P2), None)
    assert c.solo_ms == {}


# -- in the studio ------------------------------------------------------------------------


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def recording(rig: Rig, mode: str) -> None:
    studio = rig.sim.studio
    studio.features = studio.features.with_mode("seat_check", mode)  # type: ignore[arg-type]
    rig.client.post("/api/session", json={"username": "kanordm"})
    rig.client.put("/api/session/show", json={"guests": 1, "video": True, "laptop": False})
    rig.client.post("/api/recording", json={"action": "start"})


def guest_talks_at(rig: Rig, cam: CameraId, ms: int) -> None:
    rig.client.post("/api/sim/talk", json={"participant": "P2", "on": True})
    rt = rig.sim.studio.runtime
    for _ in range(ms // TICK_MS):
        for src, tile in tiles(cam).items():
            rt.feed_tile(src, tile)
        rig.run(TICK_MS)


def test_studio_on_shows_it_and_bytt_i_cutcut_swaps_the_cameras(rig: Rig) -> None:
    recording(rig, "on")
    guest_talks_at(rig, CameraId.C1, MIN_SOLO_MS + 3000)  # the guest sits at the host's camera
    seats = rig.state()["touch"]["seat_check"]
    assert seats
    assert seats[0]["id"] == "P2"
    assert "kamera 1" in seats[0]["message"] or "byttet plass" in seats[0]["message"]
    assert [a for a in rig.state()["alerts"] if a["code"] == "SEAT"]
    assert rig.client.post("/api/seat-check", json={"action": "swap"}).status_code == 200
    show = rig.sim.studio.engine.show
    assert show.participant(ParticipantId("P2")).camera is CameraId.C1
    assert rig.state()["touch"]["seat_check"] == []


def test_studio_shadow_only_logs(rig: Rig) -> None:
    recording(rig, "shadow")
    guest_talks_at(rig, CameraId.C1, MIN_SOLO_MS + 3000)
    assert rig.state()["touch"]["seat_check"] == []
    assert not [a for a in rig.state()["alerts"] if a["code"] == "SEAT"]
    assert rig.sim.studio.seat_check is None  # done: reported once
