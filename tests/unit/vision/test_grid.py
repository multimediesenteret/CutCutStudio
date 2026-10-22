"""VI-5: the 2 + 8 windows are found in a picture of the multiview, and setup step 6 turns
them into a rutekart that is saved in the app and used by the video layer at once."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from cutcut.vision.capture import SyntheticSource
from cutcut.vision.grid import find_grid, program_side
from tests.unit.vision.test_thumbs import Rig
from tests.unit.vision.test_vision import MV

cv2 = pytest.importorskip("cv2")


def close(a: tuple[float, ...], b: tuple[float, ...], tol: float = 0.01) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b, strict=True))


def picture(width: int = 960, height: int = 540) -> np.ndarray:
    frame = SyntheticSource(MV, width=width, height=height).read()
    assert frame is not None
    return frame


def test_the_windows_of_a_full_picture() -> None:
    g = find_grid(picture())
    assert g is not None
    assert g.found
    assert close(g.big[0], (0.0, 0.0, 0.5, 0.5))
    assert close(g.big[1], (0.5, 0.0, 0.5, 0.5))
    assert close(g.small[0], (0.0, 0.5, 0.25, 0.25))
    assert close(g.small[7], (0.75, 0.75, 0.25, 0.25))


def test_black_bars_and_an_offset_are_followed() -> None:
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    frame[60:1016, 110:1810] = cv2.resize(picture(), (1700, 956))
    g = find_grid(frame)
    assert g is not None
    assert g.found
    x0, y0 = 110 / 1920, 60 / 1080
    w, h = 1700 / 1920, 956 / 1080
    assert close(g.big[0], (x0, y0, w / 2, h / 2))
    assert close(g.small[5], (x0 + w / 4, y0 + h * 3 / 4, w / 4, h / 4))


def test_no_signal_and_no_grid() -> None:
    assert find_grid(np.zeros((540, 960, 3), dtype=np.uint8)) is None
    noise = np.random.default_rng(1).integers(0, 255, (540, 960, 3), dtype=np.uint8)
    g = find_grid(noise)
    assert g is not None
    assert not g.found  # the standard grid, and the technician drags the corners


def test_program_is_the_window_with_the_red_frame() -> None:
    frame = picture()
    g = find_grid(frame)
    assert g is not None
    assert program_side(frame, g) is None  # no tally in the drawing
    x, y, w, h = (round(v * n) for v, n in zip(g.big[1], (960, 540, 960, 540), strict=True))
    frame[y : y + 4, x : x + w] = (0, 0, 230)  # BGR red along the right window
    frame[y + h - 4 : y + h, x : x + w] = (0, 0, 230)
    frame[y : y + h, x : x + 4] = (0, 0, 230)
    frame[y : y + h, x + w - 4 : x + w] = (0, 0, 230)
    assert program_side(frame, g) == "right"


def w1_rect(rig: Rig) -> tuple[float, float, float, float]:
    """The window the video layer reads C1 from, right now."""
    assert rig.sim.vision is not None
    tile = rig.sim.vision.vision.mv.tile("W1")
    assert tile is not None
    return tile.rect


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def test_suggest_adjust_save_and_the_video_layer_uses_it(rig: Rig) -> None:
    c = rig.client
    rig.run(500)
    c.get("/api/vision/thumb/MV")  # the setup page shows the picture: thumbnails start
    rig.run(1000)
    assert c.get("/api/vision/thumb/MV").status_code == 200
    s = c.get("/api/setup/multiview/suggest").json()
    assert s["found"] is True
    assert "Kildene i rutene er lest fra ATEM." in s["notes"]
    m = s["map"]
    assert [t["id"] for t in m["tiles"]][:2] == ["PVW", "PGM"]
    before = c.get("/api/setup/multiview").json()["map"]
    assert [t["source"] for t in m["tiles"]] == [t["source"] for t in before["tiles"]]
    assert [t["camera"] for t in m["tiles"]] == [t["camera"] for t in before["tiles"]]

    # the technician drags a corner a little, and saves
    m["tiles"][2]["rect"] = [0.01, 0.51, 0.23, 0.23]
    r = c.put("/api/setup/multiview", json=m)
    assert r.status_code == 200, r.text
    assert r.json()["in_app"] is True
    assert r.json()["ok"] is True
    vision = rig.sim.vision
    assert vision is not None
    assert w1_rect(rig) == (0.01, 0.51, 0.23, 0.23)  # used at once
    assert "multiview:" in c.get("/api/settings/setup.yaml").text  # and saved with the setup

    # back to the file
    r = c.delete("/api/setup/multiview")
    assert r.json()["in_app"] is False
    assert w1_rect(rig) == (0.0, 0.5, 0.25, 0.25)


def test_a_map_that_reads_the_wrong_camera_is_refused(rig: Rig) -> None:
    c = rig.client
    m = c.get("/api/setup/multiview").json()["map"]
    m["tiles"][2]["camera"], m["tiles"][3]["camera"] = (
        m["tiles"][3]["camera"],
        m["tiles"][2]["camera"],
    )
    r = c.put("/api/setup/multiview", json=m)
    assert r.status_code == 409
    assert "Rutekartet kan ikke brukes" in r.json()["detail"]
    m = c.get("/api/setup/multiview").json()["map"]
    m["tiles"][2]["rect"] = [0.0, 0.4, 0.25, 0.25]  # overlaps preview
    assert c.put("/api/setup/multiview", json=m).status_code in (409, 422)


def test_without_a_picture_the_windows_stay_where_they_are(rig: Rig) -> None:
    s = rig.client.get("/api/setup/multiview/suggest").json()
    assert s["found"] is False
    assert any("ikke noe bilde" in n for n in s["notes"])
    assert s["map"]["tiles"][2]["rect"] == [0.0, 0.5, 0.25, 0.25]


def test_not_during_a_recording(rig: Rig) -> None:
    from tests.unit.api.test_api import TEST_CARD

    c = rig.client
    m = c.get("/api/setup/multiview").json()["map"]
    c.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(60)
    c.put("/api/session/show", json={"guests": 1, "video": True})
    c.post("/api/recording", json={"action": "start"})
    rig.run(4500)
    r = c.put("/api/setup/multiview", json=m)
    assert r.status_code == 409
    assert "opptak" in r.json()["detail"]
