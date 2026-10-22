"""Layouts L1–L4 (spec 5.6, P3): picture-in-picture and quad split, built by ATEM macros.

A layout replaces the base-mode shot only for speakers, crosstalk and ping-pong; it stands at
least ``L_min_s`` and is not used again within ``L_no_repeat_s``. Off by default; in shadow
it is logged and base mode cuts."""

from __future__ import annotations

from dataclasses import replace

from cutcut.common.ids import QUAD3C, QUAD4, RuleId, is_layout
from cutcut.core.inputs import ContentState
from cutcut.core.intents import PrepareLayout
from tests.rules.harness import Harness, started

ON = {"layouts": True}


def with_content(h: Harness) -> None:
    """Content active and just shown (a new slide went to program)."""
    h.content = ContentState.STATIC
    h.run(2500)
    h.content = ContentState.NEW_SLIDE
    h.run(60)
    h.content = ContentState.STATIC


def rounds(h: Harness, order: tuple[str, ...], n: int, ms: int) -> None:
    for i in range(n):
        h.stop_all()
        h.talk(order[i % len(order)])
        h.run(ms)


def layout_cuts(h: Harness) -> list[str]:
    return [d.shot for d in h.cuts() if is_layout(d.shot)]


def test_L1_speaker_with_content_gets_picture_in_picture() -> None:
    h = started(features=ON)
    h.talk("P1")
    h.run(5000)
    with_content(h)
    h.run(20000)
    assert "PIP:P1+CONTENT" in layout_cuts(h)
    assert any(d.rule is RuleId.L1 for d in h.cuts())
    assert h.intents_of(PrepareLayout)  # built by the macros, taken with MIX


def test_L1_not_without_content() -> None:
    h = started(features=ON)
    h.talk("P1")
    h.run(25000)
    assert layout_cuts(h) == []


def test_L2_ping_pong_between_two_gets_two_person_pip() -> None:
    h = started(3, features=ON)
    rounds(h, ("P1", "P2"), 12, 1800)
    assert "PIP:P1+P2" in layout_cuts(h)
    assert any(d.rule is RuleId.L2 for d in h.cuts())


def test_L2_not_when_the_layouts_switch_is_off() -> None:
    h = started(3)
    rounds(h, ("P1", "P2"), 12, 1800)
    assert layout_cuts(h) == []


def test_L3_three_voices_in_ten_seconds_give_quad_in_N4() -> None:
    h = started(4, features=ON)
    rounds(h, ("P1", "P2", "P3", "P4"), 9, 2500)
    assert QUAD4 in layout_cuts(h)
    assert any(d.rule is RuleId.L3 for d in h.cuts())


def test_L3_not_with_only_two_voices() -> None:
    h = started(4, features=ON)
    rounds(h, ("P1", "P2"), 3, 4000)
    assert QUAD4 not in layout_cuts(h)


def test_L4_three_people_with_content_get_quad_with_content() -> None:
    h = started(3, features=ON)
    with_content(h)
    rounds(h, ("P1", "P2", "P3"), 8, 2500)
    assert QUAD3C in layout_cuts(h)
    assert any(d.rule is RuleId.L4 for d in h.cuts())


def test_L4_not_without_content() -> None:
    h = started(3, features=ON)
    rounds(h, ("P1", "P2", "P3"), 8, 2500)
    assert QUAD3C not in layout_cuts(h)


def test_a_layout_stands_six_seconds_and_does_not_repeat_within_thirty() -> None:
    h = started(4, features=ON)
    rounds(h, ("P1", "P2", "P3", "P4"), 24, 2500)
    cuts = h.cuts()
    quads = [i for i, d in enumerate(cuts) if d.shot == QUAD4]
    assert quads
    for i in quads:
        if i + 1 < len(cuts):
            assert cuts[i + 1].mono_ms - cuts[i].mono_ms >= 6000
    ends = [cuts[i + 1].mono_ms for i in quads if i + 1 < len(cuts)]
    starts = [cuts[i].mono_ms for i in quads]
    for end in ends:
        later = [s for s in starts if s > end]
        if later:
            assert later[0] - end >= 30_000


def test_layouts_in_shadow_are_logged_but_base_mode_cuts() -> None:
    h = started(4, features={"shadow": ["layouts"]})
    rounds(h, ("P1", "P2", "P3", "P4"), 9, 2500)
    assert layout_cuts(h) == []
    notes = [d for d in h.decisions if d.switch == "layouts"]
    assert notes
    assert notes[0].shot == QUAD4
    assert notes[0].rule is RuleId.L3
    assert not h.intents_of(PrepareLayout)  # nothing sent to the ATEM


def test_a_show_can_leave_a_layout_out() -> None:
    h = started(4, features=ON)
    layouts = h.show.layouts.model_copy(update={"quad_four": False})
    show = h.show.model_copy(update={"layouts": layouts})
    h.engine.set_config(replace(h.engine.config, show=show))
    rounds(h, ("P1", "P2", "P3", "P4"), 9, 2500)
    assert QUAD4 not in layout_cuts(h)
