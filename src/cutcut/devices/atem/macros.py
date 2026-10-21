"""The ATEM layout macros (spec 7.2): number, name and which layout each one builds.

The layouts are made in ATEM Software Control as macros with fixed numbers and names; the
Companion page runs them (DA-9) and the engine takes the result to program with TAKE MIX.
At start-up and every 5 minutes ``H-ATEM-3`` checks that they are all there with the right
name (DA-7). If they are not, the layout switch cannot be turned on: the engine would cut to
a SuperSource that shows something else.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Macro:
    number: int  # as in ATEM Software Control and Companion (the first macro is 1)
    name: str
    shot: str | None  # the layout it builds; None for LAYOUT_RESET


LAYOUT_MACROS: Final[tuple[Macro, ...]] = (
    Macro(10, "PIP_P1_CONTENT", "PIP:P1+CONTENT"),
    Macro(11, "PIP_P2_CONTENT", "PIP:P2+CONTENT"),
    Macro(12, "PIP_P3_CONTENT", "PIP:P3+CONTENT"),
    Macro(13, "PIP_P4_CONTENT", "PIP:P4+CONTENT"),
    Macro(20, "PIP_P1_P2", "PIP:P1+P2"),
    Macro(21, "PIP_P1_P3", "PIP:P1+P3"),
    Macro(22, "PIP_P1_P4", "PIP:P1+P4"),
    Macro(23, "PIP_P2_P3", "PIP:P2+P3"),
    Macro(24, "PIP_P2_P4", "PIP:P2+P4"),
    Macro(25, "PIP_P3_P4", "PIP:P3+P4"),
    Macro(30, "QUAD4", "QUAD4"),
    Macro(31, "QUAD3C", "QUAD3C"),
    Macro(40, "LAYOUT_RESET", None),
)
BY_SHOT: Final = {m.shot: m.number for m in LAYOUT_MACROS if m.shot is not None}
LAYOUT_RESET: Final = 40


def check(found: dict[int, str]) -> list[str]:
    """Problems with the macros in the ATEM (``found``: number → name), one sentence each."""
    problems = []
    for m in LAYOUT_MACROS:
        name = found.get(m.number)
        if name is None:
            problems.append(f"Makro {m.number} {m.name} mangler")
        elif name.strip().upper() != m.name:
            problems.append(f"Makro {m.number} heter «{name}», skal være {m.name}")
    return problems
