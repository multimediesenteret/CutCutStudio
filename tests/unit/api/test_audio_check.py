"""AU-7: the audio check during the 3-2-1 countdown – who was heard, who is muted."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.unit.api.test_api import TEST_CARD, Rig


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def ready(rig: Rig, guests: int = 2) -> None:
    c = rig.client
    c.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(100)
    assert c.put("/api/session/show", json={"guests": guests, "video": True}).status_code == 200
    rig.run(100)


def test_seats_light_up_as_people_are_heard(rig: Rig) -> None:
    ready(rig)
    c = rig.client
    c.post("/api/sim/talk", json={"participant": "P1", "on": True})
    c.post("/api/sim/talk", json={"participant": "P2", "on": True, "muted": True})
    assert c.post("/api/recording", json={"action": "start"}).status_code == 200
    rig.run(1500)
    s = rig.state()
    assert s["touch"]["step"] == "countdown"
    check = {x["id"]: x for x in s["touch"]["audio_check"]}
    assert check["P1"]["heard"] is True
    assert check["P1"]["muted"] is False
    assert check["P2"]["muted"] is True  # fader down: still on the pre-fader track
    assert check["P3"]["heard"] is False


def test_when_recording_starts_the_result_is_told(rig: Rig) -> None:
    ready(rig)
    c = rig.client
    c.post("/api/sim/talk", json={"participant": "P1", "on": True})
    c.post("/api/sim/talk", json={"participant": "P2", "on": True, "muted": True})
    c.post("/api/recording", json={"action": "start"})
    rig.run(6000)
    s = rig.state()
    assert s["touch"]["step"] == "rec"
    # The user is told what to do, in one sentence, with the fader number.
    assert s["touch"]["notice"] == (
        "Gjest 1: mikrofonen er skrudd ned på mikseren. Skyv fader 2 opp."
    )
    (alert,) = [a for a in s["alerts"] if a["code"] == "LYDSJEKK"]
    assert alert["level"] == "warn"
    assert "ikke hørt: Gjest 2" in alert["message"]
    assert "dempet på mikseren: Gjest 1" in alert["message"]


def test_everyone_heard_is_quiet(rig: Rig) -> None:
    ready(rig, guests=1)
    c = rig.client
    for p in ("P1", "P2"):
        c.post("/api/sim/talk", json={"participant": p, "on": True})
    c.post("/api/recording", json={"action": "start"})
    rig.run(6000)
    s = rig.state()
    assert s["touch"]["step"] == "rec"
    assert all(x["heard"] for x in s["touch"]["audio_check"])
    assert not any(a["code"] == "LYDSJEKK" for a in s["alerts"])
    assert s["touch"]["notice"] is None
