"""F-1: every switch beyond base mode can be off, in shadow or on. In shadow its rules run and
are logged, but the cuts are those of base mode; a switch that fails goes to shadow by itself."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cutcut.common.ids import RuleId, SourceId
from cutcut.common.models.show import Features
from cutcut.core.inputs import TileFrame
from tests.rules.harness import started
from tests.unit.api.test_api import Rig


def test_modes() -> None:
    f = Features()
    assert f.mode("video_confirm") == "off"
    f = f.with_mode("video_confirm", "shadow")
    assert f.mode("video_confirm") == "shadow"
    assert f.shadow == ["video_confirm"]
    f = f.with_mode("video_confirm", "on")
    assert f.mode("video_confirm") == "on"
    assert f.shadow == []
    with pytest.raises(ValueError, match="både på og i skygge"):
        Features(video_confirm=True, shadow=["video_confirm"])
    with pytest.raises(ValueError, match="kan ikke gå i skygge"):
        Features(shadow=["bird"])


def test_shadow_logs_but_cuts_as_base_mode() -> None:
    base = started(features={})
    shadow = started(features={"shadow": ["video_confirm"]})
    for h in (base, shadow):
        h.vision = {SourceId.C2: TileFrame(face_ok=False)}
        h.talk("P2")
        h.run(3000)
    assert shadow.program == base.program == "CU:P2"  # the switch did not hold the cut
    notes = [d for d in shadow.decisions if d.switch == "video_confirm"]
    assert notes
    assert all(d.shadow for d in notes)
    assert notes[0].rule is RuleId.S2
    assert not [d for d in base.decisions if d.switch]


def test_on_acts() -> None:
    h = started(features={"video_confirm": True})
    h.vision = {SourceId.C2: TileFrame(face_ok=False)}
    h.talk("P2")
    h.run(3000)
    assert h.program != "CU:P2"


def test_shadow_notes_do_not_fill_the_log() -> None:
    h = started(features={"shadow": ["video_confirm"]})
    h.vision = {SourceId.C2: TileFrame(face_ok=False)}
    h.talk("P2")
    h.run(6000)
    notes = [d for d in h.decisions if d.switch == "video_confirm"]
    assert 1 <= len(notes) <= 4  # once, then again after 2 s at most


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def test_the_technician_sees_why_and_cannot_switch_on_what_is_missing(rig: Rig) -> None:
    c = rig.client
    switches = {s["key"]: s for s in rig.state()["rules"]["switches"]}
    assert set(switches) == {
        "video_confirm",
        "reactions",
        "framing_variety",
        "slow_zoom",
        "layouts",
        "ai_tracking",
    }
    vc = switches["video_confirm"]
    assert vc["mode"] == "off"
    assert vc["can_on"] is False
    assert "videolaget" in vc["why"]
    r = c.post("/api/features", json={"video_confirm": "shadow"})
    assert r.status_code == 409
    assert "Bryteren kan ikke slås på" in r.json()["detail"]
    # with the heavy video layer reporting faces
    rig.sim.studio.runtime.vision_status = {"faces": True}
    assert c.post("/api/features", json={"video_confirm": "shadow"}).status_code == 200
    vc = {s["key"]: s for s in rig.state()["rules"]["switches"]}["video_confirm"]
    assert vc["mode"] == "shadow"
    assert c.post("/api/features", json={"video_confirm": "off"}).status_code == 200
    assert c.post("/api/features", json={"bird": "shadow"}).status_code == 409


def test_a_failing_switch_goes_to_shadow_by_itself(rig: Rig) -> None:
    studio = rig.sim.studio
    studio.runtime.vision_status = {"faces": True}
    rig.client.post("/api/features", json={"video_confirm": True})
    studio.engine._switch_failed("video_confirm", RuntimeError("test"))
    rig.run(100)
    s = rig.state()
    vc = {x["key"]: x for x in s["rules"]["switches"]}["video_confirm"]
    assert vc["mode"] == "shadow"
    assert any(a["code"] == "F-1" for a in s["alerts"])
    assert "video_confirm" not in studio.engine.failed_switches  # runs again, in shadow
