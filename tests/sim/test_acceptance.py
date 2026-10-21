"""Acceptance criteria from spec 10.4 that can be measured without equipment."""

from __future__ import annotations

import pytest

from cutcut.common.ids import RuleId
from cutcut.common.models import Decision
from cutcut.sim import all_scenarios, load_scenario, run_scenario

SPEAKER_RULES = {RuleId.T2, RuleId.T4, RuleId.H1}
CONVERSATIONS = ["samtale-2", "panel-3", "panel-4"]


def speaker_cuts(name: str) -> list[Decision]:
    sc = load_scenario(next(p for p in all_scenarios() if p.stem == name))
    decisions = run_scenario(sc).simulation.decisions
    return [d for d in decisions if d.action == "cut" and d.rule in SPEAKER_RULES]


@pytest.mark.parametrize("name", CONVERSATIONS)
def test_90_percent_of_speaker_cuts_on_K1_or_K2(name: str) -> None:
    cuts = speaker_cuts(name)
    good = [d for d in cuts if d.measures.get("cut_point") in (1, 2)]
    assert cuts
    assert len(good) / len(cuts) >= 0.90


@pytest.mark.parametrize("name", CONVERSATIONS)
def test_preview_at_least_300_ms_before_program_in_95_percent(name: str) -> None:
    cuts = speaker_cuts(name)
    good = [d for d in cuts if d.measures.get("preview_ms", 0) >= 300]
    assert len(good) / len(cuts) >= 0.95


# "Cut within 150 ms of confirmation" is tested without other rules in the way in
# tests/rules/test_talk.py::test_T2_fires_after_confirm_time.
