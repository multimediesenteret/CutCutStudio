"""DA-9: CutCut's Companion pages are made from the studio setup and committed up to date."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cutcut.common.config import load_site
from cutcut.common.ids import SourceId
from cutcut.devices.companion import pages

ROOT = Path(__file__).resolve().parents[3]
STUDIOS = ["multimediesenteret", "example"]


def buttons(page: dict[str, Any]) -> dict[tuple[int, int], tuple[str, str, dict[str, Any]]]:
    out = {}
    for r, row in page["page"]["controls"].items():
        for c, b in row.items():
            (a,) = b["steps"]["0"]["action_sets"]["down"]
            out[(int(r), int(c))] = (b["style"]["text"], a["definitionId"], a["options"])
    return out


@pytest.mark.parametrize("studio", STUDIOS)
def test_committed_files_are_up_to_date(studio: str) -> None:
    site = load_site(ROOT / "site" / studio)
    stale = pages.write(site, pages.default_out(site), check=True)
    assert stale == [], f"kjør «uv run cutcut companion-pages --site site/{studio}»"


def test_page_10_has_exactly_the_buttons_the_engine_presses() -> None:
    site = load_site(ROOT / "site" / "multimediesenteret")
    got = buttons(pages.engine_page(site))
    cmap = site.companion_map
    # Row 0: preview, with the studio's ATEM inputs (D-054: bird on 6, laptop on 7).
    c1 = cmap.preview[SourceId.C1]
    assert got[(c1.row, c1.col)][1:] == (
        "preview",
        {"mixeffect": 0, "input": 1},
    )
    assert got[(0, 4)][2]["input"] == 6
    assert got[(0, 5)][2]["input"] == 7
    assert got[(0, 7)][2]["input"] == 6000  # SuperSource
    assert (0, 6) not in got  # C7 is not wired in this studio
    # Rows 1–2: layout macros from spec 7.2; «Layout av» is macro 40.
    for shot, b in cmap.layouts.items():
        assert got[(b.row, b.col)][1:] == (
            "macrorun",
            {"macro": pages.LAYOUT_MACROS[shot], "action": "run"},
        )
    assert got[(1, 4)][2]["macro"] == 40
    # Row 3: TAKE.
    assert got[(3, 0)][1] == "cut"
    assert got[(3, 1)][1] == "auto"


def test_page_11_cuts_straight_to_program_and_has_kun_lyd() -> None:
    site = load_site(ROOT / "site" / "multimediesenteret")
    got = buttons(pages.operator_page(site))
    assert got[(2, 0)][1:] == ("program", {"mixeffect": 0, "input": 1})
    assert got[(3, 0)][1:] == ("program", {"mixeffect": 0, "input": 3010})  # media player 1
    assert {v[1] for v in got.values()} == {"program"}


def test_files_are_companion_page_exports() -> None:
    site = load_site(ROOT / "site" / "multimediesenteret")
    for page_no, make in ((10, pages.engine_page), (11, pages.operator_page)):
        f = make(site)
        assert (f["version"], f["type"], f["oldPageNumber"]) == (12, "page", page_no)
        assert f["page"]["gridSize"] == {"minColumn": 0, "maxColumn": 7, "minRow": 0, "maxRow": 3}
        (conn,) = f["instances"].values()
        assert conn["moduleId"] == "bmd-atem"
        for row in f["page"]["controls"].values():
            for b in row.values():
                assert b["type"] == "button"
                (a,) = b["steps"]["0"]["action_sets"]["down"]
                assert a["connectionId"] in f["instances"]
                assert a["upgradeIndex"] == conn["lastUpgradeIndex"]


def test_variables_carry_the_page_version_H_COMP_1() -> None:
    site = load_site(ROOT / "site" / "multimediesenteret")
    f = pages.variables_file(site)
    assert f["type"] == "full"
    assert set(f) == {
        "version",
        "type",
        "companionBuild",
        "custom_variables",
        "customVariablesCollections",
    }  # nothing else is touched on import
    v = f["custom_variables"]
    assert v["cutcut_pages_version"]["defaultValue"] == str(site.devices.companion.pages_version)
    for name in ("regi_shot", "regi_rule", "regi_reason", "regi_mode", "regi_auto"):
        assert name in v


def test_every_variable_the_executor_writes_exists() -> None:
    """The executor sets regi_* over HTTP; Companion only accepts variables that exist."""
    import re

    src = (ROOT / "src" / "cutcut").rglob("*.py")
    used = {m for p in src for m in re.findall(r"\bregi_[a-z_]+\b", p.read_text(encoding="utf-8"))}
    assert used <= set(pages.ENGINE_VARIABLES)


def test_cli_check(tmp_path: Path) -> None:
    from cutcut.__main__ import main

    assert main(["companion-pages", "--site", str(ROOT / "site" / "example"), "--check"]) == 0
    assert (
        main(
            [
                "companion-pages",
                "--site",
                str(ROOT / "site" / "example"),
                "--out",
                str(tmp_path),
                "--check",
            ]
        )
        == 1
    )
    assert (
        main(["companion-pages", "--site", str(ROOT / "site" / "example"), "--out", str(tmp_path)])
        == 0
    )
    assert json.loads((tmp_path / "cutcut-side-10.companionconfig").read_text())["type"] == "page"
