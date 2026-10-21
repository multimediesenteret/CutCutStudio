from __future__ import annotations

import re
from pathlib import Path

import pytest

from cutcut.common.ids import (
    QUAD3C,
    QUAD4,
    Mode,
    ParticipantId,
    RuleId,
    close_up,
    is_layout,
    is_shot,
    pip_content,
    pip_two,
    shot_participants,
)

SPEC = Path(__file__).parents[3] / "docs" / "spec" / "01-app-spesifikasjon.md"


@pytest.mark.parametrize(
    ("participants", "content", "audio_only", "expected"),
    [
        (1, False, False, Mode.N1),
        (2, True, False, Mode.N2C),
        (4, False, False, Mode.N4),
        (3, True, True, Mode.A),
    ],
)
def test_mode_for_show(participants: int, content: bool, audio_only: bool, expected: Mode) -> None:
    assert Mode.for_show(participants, content, audio_only) is expected


def test_mode_rejects_bad_count() -> None:
    with pytest.raises(ValueError, match="1–4"):
        Mode.for_show(5, False)


def test_mode_properties() -> None:
    assert Mode.N3C.participants == 3
    assert Mode.N3C.content
    assert not Mode.N3.content
    assert Mode.A.participants is None


@pytest.mark.parametrize(
    "shot",
    ["BIRD", "WIDE", "CONTENT", "CU:P1", "CU:P4", "PIP:P2+CONTENT", "PIP:P1+P3", "QUAD4", "QUAD3C"],
)
def test_valid_shots(shot: str) -> None:
    assert is_shot(shot)


@pytest.mark.parametrize("shot", ["CU:P5", "PIP:P3+P1", "PIP:P2+P2", "cu:p1", "C1", ""])
def test_invalid_shots(shot: str) -> None:
    assert not is_shot(shot)


def test_shot_helpers() -> None:
    assert close_up(ParticipantId.P2) == "CU:P2"
    assert pip_content(ParticipantId.P1) == "PIP:P1+CONTENT"
    assert pip_two(ParticipantId.P3, ParticipantId.P1) == "PIP:P1+P3"
    assert shot_participants("PIP:P1+P3") == (ParticipantId.P1, ParticipantId.P3)
    assert shot_participants("BIRD") == ()
    assert len(shot_participants(QUAD4)) == 4
    assert len(shot_participants(QUAD3C)) == 3
    assert is_layout("PIP:P1+CONTENT")
    assert not is_layout("CU:P1")


def test_every_rule_id_in_spec_is_known() -> None:
    """Rule IDs in the spec tables must exist in RuleId, and vice versa (spec 12.1)."""
    text = SPEC.read_text(encoding="utf-8")
    in_spec = set(re.findall(r"^\| `((?:T|B|CT|L|S|PV|K|H|R|F|Z|AT|V)\d+)` \|", text, re.M))
    known = {r.value for r in RuleId} - {"MANUAL"}
    assert in_spec, "found no rule tables in the spec"
    assert in_spec <= known, f"missing in RuleId: {sorted(in_spec - known)}"
    assert known <= in_spec, f"not in the spec tables: {sorted(known - in_spec)}"
