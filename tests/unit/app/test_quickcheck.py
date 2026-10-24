"""P14 «Sjekk dagens oppsett»: health, multiview, a name round and, optionally, colour."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from cutcut.app.quickcheck import HEARD_MS, NAME_ROUND_MS, QuickCheck
from cutcut.app.seatcheck import Seat
from cutcut.common.ids import CameraId, MicId, ParticipantId, SourceId
from cutcut.core.inputs import MicFrame, TileFrame
from cutcut.core.runtime import TICK_MS
from cutcut.health.model import CheckResult
from tests.unit.api.test_api import Rig

P1, P2 = ParticipantId("P1"), ParticipantId("P2")
SEATS = {P1: Seat(MicId.M1, CameraId.C1), P2: Seat(MicId.M2, CameraId.C2)}
NAMES = {P1: "Ola", P2: "Kari"}
TS = datetime(2026, 11, 4, 9, tzinfo=UTC)


def green() -> list[CheckResult]:
    return [CheckResult(id="H-ATEM-1", status="green", value="ok", message="ok", ts=TS)]


def mv_ok() -> dict[str, Any]:
    return {"findings": [], "readback": {"windows": []}}


def say(q: QuickCheck, who: ParticipantId | None, cam: CameraId | None, ms: int, t0: int) -> int:
    on = MicFrame(vad=0.9, level_db=-20, dominance_db=15)
    off = MicFrame(vad=0.05, level_db=-60, dominance_db=-15)
    t = t0
    for _ in range(ms // 100):
        mics = {s.mic: (on if p == who else off) for p, s in SEATS.items()}
        tiles = {
            SourceId(c.value): TileFrame(face_ok=True, mouth=0.8 if c == cam else 0.0)
            for c in (CameraId.C1, CameraId.C2, CameraId.C3, CameraId.C4)
        }
        t += 100
        q.tick(t, 100, mics, tiles)
    return t


def test_all_good() -> None:
    q = QuickCheck(0, dict(SEATS), NAMES, green, mv_ok)
    t = say(q, P1, CameraId.C1, HEARD_MS + 200, 0)
    say(q, P2, CameraId.C2, HEARD_MS + 200, t)
    assert q.phase == "ferdig"
    assert [s.result for s in q.steps] == ["ok", "ok", "ok", "hoppet over"]
    assert q.result == "ok"


def test_someone_silent_and_someone_in_the_wrong_seat() -> None:
    red = [CheckResult(id="H-PRL-1", status="red", value="nede", message="x", ts=TS)]
    q = QuickCheck(0, dict(SEATS), NAMES, lambda: red, mv_ok)
    say(q, P2, CameraId.C1, NAME_ROUND_MS + 100, 0)  # only Kari talks, at Ola's camera
    assert q.phase == "ferdig"
    assert q.steps[0].result == "feil"
    assert "H-PRL-1" in q.steps[0].summary
    assert q.steps[2].result == "feil"
    assert "Ikke hørt: Ola" in q.steps[2].summary
    assert "Kari ser ut til å sitte ved kamera 1" in q.steps[2].summary
    assert q.result == "feil"


def test_colour_with_a_grey_card() -> None:
    def card(rb: float) -> np.ndarray:
        img = np.zeros((90, 160, 3), dtype=np.uint8)
        img[:] = (40, 60, 80)
        img[20:70, 50:110] = (int(128 / rb), 128, int(128 * rb))  # BGR grey-ish card
        return img

    frames = {CameraId.C1: card(1.0), CameraId.C2: card(1.08)}  # C2 is a little warmer
    q = QuickCheck(0, dict(SEATS), NAMES, green, mv_ok, grab=frames.get)
    t = say(q, P1, CameraId.C1, HEARD_MS + 200, 0)
    say(q, P2, CameraId.C2, HEARD_MS + 200, t)
    assert q.steps[3].result == "advarsel"
    assert "C2:" in q.steps[3].summary
    assert "% i farge" in q.steps[3].summary


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def test_in_the_studio(rig: Rig) -> None:
    r = rig.client.post("/api/quick-check", json={"color": False})
    assert r.status_code == 200
    assert r.json()["phase"] == "navnerunde"
    assert rig.client.post("/api/quick-check", json={}).status_code == 409  # already running
    rt = rig.sim.studio.runtime
    show = rig.sim.studio.engine.show
    for p in show.participants:
        rig.client.post("/api/sim/talk", json={"participant": p.id.value, "on": True})
        for _ in range((HEARD_MS + 500) // TICK_MS):
            for c in (CameraId.C1, CameraId.C2, CameraId.C3, CameraId.C4):
                rt.feed_tile(
                    SourceId(c.value), TileFrame(face_ok=True, mouth=0.8 if c == p.camera else 0)
                )
            rig.run(TICK_MS)
        rig.client.post("/api/sim/talk", json={"participant": p.id.value, "on": False})
        rig.run(300)
    info = rig.client.get("/api/quick-check").json()
    assert info["phase"] == "ferdig"
    assert info["steps"][2]["result"] == "ok", info
    assert info["at"]
