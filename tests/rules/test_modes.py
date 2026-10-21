"""Modes N1–N4C and their shot tables (spec 5.1)."""

from __future__ import annotations

import pytest

from cutcut.common.ids import BIRD, CONTENT, WIDE, Mode
from cutcut.core import shots
from tests.rules.harness import make_show


@pytest.mark.parametrize(
    ("participants", "wide", "crosstalk", "silence"),
    [
        (1, False, None, BIRD),
        (1, True, None, WIDE),
        (2, False, BIRD, BIRD),
        (2, True, WIDE, WIDE),
        (3, False, BIRD, BIRD),
        (3, True, BIRD, BIRD),
        (4, False, BIRD, BIRD),
    ],
)
def test_mode_shot_tables(
    participants: int, wide: bool, crosstalk: str | None, silence: str
) -> None:
    show = make_show(participants, wide=wide)
    mode = Mode.for_show(participants, False)
    assert shots.crosstalk_shot(mode, show, show.features) == crosstalk
    assert shots.silence_shot(mode, show, show.features) == silence
    assert shots.pingpong_shot(mode, show, show.features) == crosstalk
    assert shots.fallback_shot(mode, show, show.features) == BIRD


@pytest.mark.parametrize("participants", [1, 2, 3, 4])
def test_content_modes_use_content_for_silence(participants: int) -> None:
    show = make_show(participants)
    mode = Mode.for_show(participants, True)
    assert mode.content
    assert shots.silence_shot(mode, show, show.features) == CONTENT


def test_shot_source_mapping_round_trips() -> None:
    show = make_show(4, wide=True)
    for shot in ("CU:P1", "CU:P4", BIRD, WIDE, CONTENT):
        assert shots.shot_for(shots.source_for(shot, show), show) == shot


def test_without_bird_switch_fallback_is_wide_then_host() -> None:
    show = make_show(2, wide=True, features={"bird": False})
    assert shots.fallback_shot(Mode.N2, show, show.features) == WIDE
    show = make_show(2, features={"bird": False})
    assert shots.fallback_shot(Mode.N2, show, show.features) == "CU:P1"
