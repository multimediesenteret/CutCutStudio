"""Every scenario in sim/scenarios/ runs and meets its expectations (SIM-2, SIM-5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from cutcut.sim import all_scenarios, load_scenario, run_scenario


@pytest.mark.parametrize("path", all_scenarios(), ids=lambda p: p.stem)
def test_scenario_meets_expectations(path: Path) -> None:
    result = run_scenario(load_scenario(path))
    assert result.passed, "\n".join(result.failures)


def test_there_are_scenarios_for_every_group_size_and_fault() -> None:
    scenarios = [load_scenario(p) for p in all_scenarios()]
    shows = {s.show for s in scenarios}
    assert {"solo", "samtale", "panel-3", "panel-4"} <= shows
    faults = {f.kind for s in scenarios for f in s.faults}
    assert {"audio_lost", "camera_moving", "companion_down"} <= faults


def test_same_seed_gives_same_conversation() -> None:
    sc = load_scenario(next(p for p in all_scenarios() if p.stem == "samtale-2"))
    a = run_scenario(sc).simulation.decisions
    b = run_scenario(sc).simulation.decisions
    assert [d.model_dump() for d in a] == [d.model_dump() for d in b]
