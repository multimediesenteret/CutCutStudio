"""SE-6: the studio's show type decides (D-036), and «Kun lyd» records audio with the graphic
on program and no camera ever moved. SE-7: Panopto is shown as prepared, nothing is promised."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cutcut.common.ids import SourceId
from cutcut.core.intents import DirectCut, PrepareLayout, SetPreview, ShowAudioOnly, Take
from tests.unit.api.test_api import TEST_CARD, Rig


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def start(rig: Rig, guests: int = 1, video: bool = True) -> None:
    c = rig.client
    c.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(60)
    c.put("/api/session/show", json={"guests": guests, "video": video, "type": "panel"})
    c.post("/api/recording", json={"action": "start"})
    rig.run(4500)


def test_the_studio_type_decides_not_the_touch_screen(rig: Rig) -> None:
    c = rig.client
    assert rig.state()["studio"]["show_type"] == "podcast"
    assert c.put("/api/settings/show-type", json={"type": "intervju"}).status_code == 200
    start(rig)  # the touch screen sends «panel»: ignored
    s = rig.state()
    assert s["session"]["show"]["type"] == "intervju"
    assert s["rules"]["preset"] == "rolig"  # intervju → rolig (show_types.yaml)


def test_unknown_type_is_refused(rig: Rig) -> None:
    r = rig.client.put("/api/settings/show-type", json={"type": "talkshow"})
    assert r.status_code == 409
    assert "Velg en av" in r.json()["detail"]


def test_kun_lyd_records_audio_with_the_graphic_and_moves_nothing(rig: Rig) -> None:
    c = rig.client
    c.put("/api/settings/show-type", json={"type": "kun-lyd"})
    sent: list[object] = []
    atem = rig.sim.atem
    original = atem.submit

    def spy(intent: object) -> None:
        sent.append(intent)
        original(intent)  # type: ignore[arg-type]

    atem.submit = spy  # type: ignore[method-assign]
    start(rig, guests=2, video=True)  # even if touch asks for video
    c.post("/api/sim/talk", json={"participant": "P2", "on": True})
    rig.run(8000)
    s = rig.state()
    assert s["session"]["show"]["video"] is False
    assert s["engine"]["mode"] == "A"
    assert s["recording"]["pearl"] == "started"  # recorded as usual
    assert rig.sim.atem.program is SourceId.SUPERSOURCE  # the «Kun lyd» graphic
    assert any(isinstance(i, ShowAudioOnly) for i in sent)
    cuts = [i for i in sent if isinstance(i, SetPreview | Take | DirectCut | PrepareLayout)]
    assert cuts == []  # no cutting to cameras in mode A


def test_iso_follows_the_type(rig: Rig) -> None:
    studio = rig.sim.studio
    assert studio.iso_wanted() is False
    types = studio.deps.show_types.types
    patched = {**types, "podcast": types["podcast"].model_copy(update={"iso_record": True})}
    studio.deps.show_types = studio.deps.show_types.model_copy(update={"types": patched})
    assert studio.iso_wanted() is True


def test_the_type_is_saved_with_the_setup(rig: Rig) -> None:
    c = rig.client
    c.put("/api/settings/show-type", json={"type": "panel"})
    text = c.get("/api/settings/setup.yaml").text
    assert "show_type: panel" in text
    c.put("/api/settings/show-type", json={"type": "podcast"})
    check = c.post("/api/settings/setup/check", json={"text": text}).json()["changes"]
    assert "Show-type: Panel" in check
    c.post("/api/settings/setup/import", json={"text": text})
    assert rig.state()["studio"]["show_type"] == "panel"


def test_panopto_is_prepared_not_promised(rig: Rig) -> None:
    start(rig)
    assert rig.state()["session"]["publish"]["state"] == "disabled"
