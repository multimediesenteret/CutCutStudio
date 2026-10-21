"""D-055: the multiview is checked against the rutekart, the shows and the ATEM."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from cutcut.common.config import example_site_dir, load_site
from cutcut.common.ids import SourceId
from cutcut.common.models.multiview import MultiviewMap, MultiviewReadback, Tile
from cutcut.setup.multiview import (
    StudioInputs,
    check_map,
    check_readback,
    compare_recommended,
    readback_from_map,
    recommended,
)

NTNU = Path(__file__).resolve().parents[3] / "site" / "ntnu-studio"


def _site(path: Path):  # type: ignore[no-untyped-def]
    site = load_site(path)
    return site, StudioInputs.from_site(site)


def test_ntnu_map_matches_its_shows() -> None:
    site, inputs = _site(NTNU)
    assert site.multiview is not None
    assert check_map(site.multiview, inputs) == []


def test_example_map_is_the_recommended_one() -> None:
    site, inputs = _site(example_site_dir())
    assert site.multiview is not None
    assert check_map(site.multiview, inputs) == []
    assert compare_recommended(site.multiview, recommended(inputs)) == []


def test_recommended_layout_for_ntnu_studio() -> None:
    _, inputs = _site(NTNU)
    rec = recommended(inputs)
    small = [(t.id, t.source, t.camera) for t in rec.small_windows()]
    assert small == [
        ("W1", "input1", SourceId.C1),
        ("W2", "input2", SourceId.C2),
        ("W3", "input3", SourceId.C3),
        ("W4", "input4", SourceId.C4),
        ("W5", "input6", SourceId.C5),
        ("W6", "input7", SourceId.LAPTOP),
        ("W7", "supersource", SourceId.SUPERSOURCE),
        ("W8", "mediaplayer1", None),
    ]
    assert rec.preview_left


def test_today_ntnu_differs_only_where_cutcut_does_not_read() -> None:
    site, inputs = _site(NTNU)
    assert site.multiview is not None
    suggestions = compare_recommended(site.multiview, recommended(inputs))
    assert {f.where for f in suggestions} == {"rute W7", "rute W8"}
    assert all(f.level == "info" for f in suggestions)


def test_map_pointing_at_the_wrong_input_is_an_error() -> None:
    site, inputs = _site(NTNU)
    assert site.multiview is not None
    tiles = [
        t.model_copy(update={"source": "input5"}) if t.id == "W5" else t
        for t in site.multiview.tiles
    ]
    wrong = site.multiview.model_copy(update={"tiles": tiles})
    findings = check_map(wrong, inputs)
    assert [f.check for f in findings] == ["H-MV-2"]
    assert "fugleperspektivet" in findings[0].message
    assert "Camera 6" in findings[0].message


def test_map_without_a_camera_is_an_error() -> None:
    site, inputs = _site(NTNU)
    assert site.multiview is not None
    tiles = [
        t.model_copy(update={"camera": None}) if t.id == "W6" else t for t in site.multiview.tiles
    ]
    findings = check_map(site.multiview.model_copy(update={"tiles": tiles}), inputs)
    assert [f.check for f in findings] == ["H-MV-1"]
    assert "W6" in findings[0].fix
    assert check_map(None, inputs)[0].check == "H-MV-0"


def test_atem_that_matches_gives_no_findings() -> None:
    site, _ = _site(NTNU)
    assert site.multiview is not None
    assert check_readback(site.multiview, readback_from_map(site.multiview)) == []


def test_atem_with_swapped_cameras_safe_area_and_swapped_preview() -> None:
    site, _ = _site(NTNU)
    mv = site.multiview
    assert mv is not None
    rb = readback_from_map(mv)
    w = list(rb.windows)
    w[0], w[1] = w[1], w[0]
    w[7] = "black"  # opptaksstatus replaced: not read by CutCut, only a warning
    bad = rb.model_copy(update={"windows": w, "safe_area": True, "preview_left": False})
    findings = check_readback(mv, bad)
    by = [(f.check, f.level, f.where) for f in findings]
    assert ("H-MV-4", "error", "preview/program") in by
    assert ("H-MV-5", "error", "rute W1") in by
    assert ("H-MV-5", "error", "rute W2") in by
    assert ("H-MV-5", "warn", "rute W8") in by
    assert ("H-MV-6", "warn", "overlegg") in by


def test_wrong_layout_stops_further_checks() -> None:
    site, _ = _site(NTNU)
    assert site.multiview is not None
    rb = MultiviewReadback(layout="other", windows=["black"] * 8)
    assert [f.check for f in check_readback(site.multiview, rb)] == ["H-MV-3"]


def test_no_readback_yet_is_only_info() -> None:
    site, _ = _site(NTNU)
    assert site.multiview is not None
    assert [f.level for f in check_readback(site.multiview, None)] == ["info"]


@pytest.mark.parametrize(
    ("tiles", "msg"),
    [
        ([("PVW", (0, 0, 0.5, 0.5), "preview"), ("PGM", (0.4, 0, 0.5, 0.5), "program")], "overlap"),
        (
            [("PVW", (0, 0, 0.5, 0.5), "preview"), ("PGM", (0.5, 0, 0.5, 0.5), "preview")],
            "exactly one",
        ),
        ([("PVW", (0, 0, 0.5, 0.5), "preview"), ("PGM", (0.6, 0, 0.5, 0.5), "program")], "inside"),
    ],
)
def test_bad_maps_are_refused(tiles: list[tuple[str, tuple[float, ...], str]], msg: str) -> None:
    with pytest.raises(ValidationError, match=msg):
        MultiviewMap(tiles=[Tile(id=i, rect=r, source=s) for i, r, s in tiles])  # type: ignore[arg-type]


def test_camera_must_be_read_from_an_input() -> None:
    with pytest.raises(ValidationError, match="input source"):
        Tile(id="W1", rect=(0, 0.5, 0.25, 0.25), source="mediaplayer1", camera=SourceId.C1)
