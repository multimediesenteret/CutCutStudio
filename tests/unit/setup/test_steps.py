"""HS-5: the setup steps are data, the guide is made from them, and a step's state follows its
health checks."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from tools.gen_setup_guide import OUT, render

from cutcut.health.model import CheckResult
from cutcut.setup.steps import (
    Approval,
    StepsError,
    load_steps,
    results_for,
    step_state,
)

ROOT = Path(__file__).resolve().parents[3]
DEFAULTS = ROOT / "config" / "defaults" / "setup"
T0 = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)


def result(cid: str, status: str = "green") -> CheckResult:
    return CheckResult(id=cid, status=status, value="v", message="m", ts=T0)  # type: ignore[arg-type]


def test_the_ten_steps_load_in_order() -> None:
    steps = load_steps(DEFAULTS)
    assert [s.number for s in steps] == list(range(1, 11))
    assert steps[2].id == "atem"
    assert steps[2].fix is not None
    assert steps[9].checks == []  # the dress rehearsal is approved by the technician


def test_a_studio_file_replaces_the_default(tmp_path: Path) -> None:
    text = (DEFAULTS / "07-companion.yaml").read_text(encoding="utf-8")
    (tmp_path / "07-companion.yaml").write_text(
        text.replace('title: "Companion"', 'title: "Companion i rack"'), encoding="utf-8"
    )
    steps = load_steps(DEFAULTS, tmp_path)
    assert len(steps) == 10
    assert steps[6].title == "Companion i rack"


def test_a_bad_step_is_refused_with_the_file_name(tmp_path: Path) -> None:
    (tmp_path / "03-feil.yaml").write_text(
        "number: 3\nid: atem\ntitle: x\nwhy: y\nhow: [z]\n", encoding="utf-8"
    )
    with pytest.raises(StepsError, match=r"03-feil\.yaml"):
        load_steps(tmp_path)
    (tmp_path / "03-feil.yaml").write_text(
        "number: 3\nid: feil\ntitle: x\nwhy: y\nhow: [z]\nchecks: [ATEM]\n", encoding="utf-8"
    )
    with pytest.raises(StepsError, match="ikke en helsesjekk"):
        load_steps(tmp_path)


def test_checks_match_with_wildcards() -> None:
    cams = load_steps(DEFAULTS)[3]
    found = results_for(cams, [result("H-CAM-C2"), result("H-CAM-MOVE"), result("H-ATEM-1")])
    assert [r.id for r in found] == ["H-CAM-C2", "H-CAM-MOVE"]


def test_state_red_beats_an_old_approval() -> None:
    step = load_steps(DEFAULTS)[2]
    ok = Approval(by="tekniker", at=T0)
    assert step_state(step, [], None) == "not_checked"
    assert step_state(step, [result("H-ATEM-1")], None) == "green"
    assert step_state(step, [result("H-ATEM-1")], ok) == "approved"
    assert step_state(step, [result("H-ATEM-1"), result("H-ATEM-2", "yellow")], ok) == "yellow"
    assert step_state(step, [result("H-ATEM-1", "red")], ok) == "red"


def test_the_printed_guide_is_current() -> None:
    assert OUT.read_text(encoding="utf-8") == render(), (
        "docs/setup/README.md er utdatert: uv run python tools/gen_setup_guide.py"
    )
