"""Simulator: synthetic talkers, fake devices, scenarios and traces (docs/plans/sim.md)."""

from cutcut.sim.scenario import Scenario, all_scenarios, load_scenario
from cutcut.sim.simulation import ScenarioResult, Simulation, build_show, run_scenario

__all__ = [
    "Scenario",
    "ScenarioResult",
    "Simulation",
    "all_scenarios",
    "build_show",
    "load_scenario",
    "run_scenario",
]
