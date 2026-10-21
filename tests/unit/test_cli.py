from __future__ import annotations

import socket
from pathlib import Path

import pytest

from cutcut import __version__
from cutcut.__main__ import main
from cutcut.sim.serve import SimOptions, banner


def test_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_arguments_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "CutCut Studio" in capsys.readouterr().out


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_sim_smoke_starts_engine_and_serves_screens(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """SIM-6: the README command, end to end over real HTTP."""
    for screen in ("touch", "tech"):
        (tmp_path / screen).mkdir()
        (tmp_path / screen / "index.html").write_text('<div id="root"></div>')
    rc = main(["sim", "--smoke", "--port", str(_free_port()), "--ui-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "/touch/: ok" in out
    assert "/tech/: ok" in out


def test_sim_banner_says_when_screens_are_not_built(tmp_path: Path) -> None:
    text = banner(SimOptions(ui_dir=tmp_path / "missing"))
    assert "/touch/" in text
    assert "pnpm build" in text
