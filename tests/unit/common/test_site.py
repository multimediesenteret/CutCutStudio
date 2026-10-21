from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cutcut.common.config import ConfigError, example_site_dir, load_site
from cutcut.common.ids import SourceId


def test_example_site_loads_with_shows_for_one_to_four() -> None:
    site = load_site(example_site_dir())
    sizes = sorted(len(s.participants) for s in site.shows.values())
    assert sizes == [1, 2, 3, 4]
    assert site.devices.studio == "example"
    assert site.staff.role_of("admin1") == "admin"
    assert site.staff.role_of("tekniker1") == "operator"
    assert site.staff.role_of("ukjent") is None
    assert site.companion_map.preview[SourceId.C2].col == 1
    assert site.companion_map.layouts["QUAD4"].row == 2


def copy_site(tmp_path: Path) -> Path:
    dest = tmp_path / "site"
    shutil.copytree(example_site_dir(), dest)
    return dest


def test_show_with_wrong_camera_ip_is_refused(tmp_path: Path) -> None:
    root = copy_site(tmp_path)
    show = root / "shows" / "samtale.yaml"
    show.write_text(show.read_text().replace("10.10.10.22", "10.10.10.99"))
    with pytest.raises(ConfigError, match=r"devices\.yaml sier"):
        load_site(root)


def test_duplicate_companion_button_is_refused(tmp_path: Path) -> None:
    root = copy_site(tmp_path)
    path = root / "equipment" / "companion_map.yaml"
    path.write_text(path.read_text().replace("C2: { row: 0, col: 1 }", "C2: { row: 0, col: 0 }"))
    with pytest.raises(ConfigError, match="same Companion button"):
        load_site(root)


def test_no_secrets_or_card_numbers_in_example_site() -> None:
    for path in example_site_dir().rglob("*.yaml"):
        text = path.read_text().lower()
        assert "password:" not in text
        assert "api_key" not in text
        assert "uid" not in text
