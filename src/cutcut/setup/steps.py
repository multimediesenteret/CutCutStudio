"""The setup helper's ten steps as data (spec 8.4, HS-5).

Each step is one YAML file in ``config/defaults/setup/NN-<id>.yaml``: what and why, how to do it
(with the expected values in **bold**), which health checks show the result, and whether CutCut
can fix it itself («Fiks for meg»). A studio can replace a step with a file of the same name in
``site/<studio>/setup/``. The same files give the wizard on the technician screen and the
printed guide in ``docs/setup/`` (``tools/gen_setup_guide.py``), so the two never differ.

The wizard never runs anything that moves a camera or changes the ATEM during a recording; the
checks it runs are the ordinary health checks, which only read.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from ruamel.yaml import YAML

from cutcut.health.model import CheckResult

FixAction = Literal["atem_input_names"]
Panel = Literal["devices", "atem", "mics", "multiview"]
StepState = Literal["not_checked", "red", "yellow", "green", "approved"]


class Fix(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: FixAction
    label: str
    confirm: str  # shown before CutCut changes anything


class SetupStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    number: int = Field(ge=1, le=99)
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    title: str
    why: str  # «Hva og hvorfor»: one sentence
    how: list[str] = Field(min_length=1)  # «Slik gjør du»; expected values in **bold**
    checks: list[str] = Field(default_factory=list)  # health check IDs, «*» allowed
    fix: Fix | None = None
    panel: Panel | None = None  # the part of the setup page that belongs to this step

    @field_validator("checks")
    @classmethod
    def _ids(cls, v: list[str]) -> list[str]:
        for c in v:
            if not c.startswith("H-"):
                raise ValueError(f"«{c}» er ikke en helsesjekk (H-…)")
        return v

    def matches(self, check_id: str) -> bool:
        return any(fnmatchcase(check_id, pattern) for pattern in self.checks)


class StepsError(ValueError):
    """A step file cannot be used. ``str()`` is Norwegian."""


def load_steps(*folders: Path) -> list[SetupStep]:
    """All ``NN-*.yaml`` in the folders; a later folder replaces a file of the same name."""
    files: dict[str, Path] = {}
    for folder in folders:
        if folder.is_dir():
            for p in sorted(folder.glob("[0-9][0-9]-*.yaml")):
                files[p.name] = p
    yaml = YAML(typ="safe")
    steps: list[SetupStep] = []
    for name in sorted(files):
        try:
            step = SetupStep.model_validate(yaml.load(files[name].read_text(encoding="utf-8")))
        except Exception as exc:
            raise StepsError(f"{name}: {exc}") from exc
        if not name.startswith(f"{step.number:02d}-{step.id}"):
            raise StepsError(f"{name}: filnavnet skal være {step.number:02d}-{step.id}.yaml")
        steps.append(step)
    numbers = [s.number for s in steps]
    if len(set(numbers)) != len(numbers):
        raise StepsError("to setup-steg har samme nummer")
    return steps


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    by: str
    at: datetime
    note: str | None = None


class StepView(BaseModel):
    """One step as the wizard shows it: the text, and the checks side by side."""

    step: SetupStep
    state: StepState
    results: list[CheckResult]
    approved: Approval | None = None
    fix_available: bool = False
    fix_blocked: str | None = None  # why «Fiks for meg» cannot be used now


RANK = {"green": 0, "yellow": 1, "red": 2}


def step_state(
    step: SetupStep, results: Sequence[CheckResult], approved: Approval | None
) -> StepState:
    """Red or yellow wins over an approval: an approved step that is red now is not ready."""
    if results:
        worst = max(results, key=lambda r: RANK[r.status]).status
        if worst != "green":
            return worst
        return "approved" if approved else "green"
    return "approved" if approved else "not_checked"


def results_for(step: SetupStep, results: Iterable[CheckResult]) -> list[CheckResult]:
    return sorted((r for r in results if step.matches(r.id)), key=lambda r: r.id)


def guide_markdown(steps: Sequence[SetupStep]) -> str:
    """The printed setup guide (spec 12.1), from the same files as the wizard."""
    out = [
        "# Oppsettsguide",
        "",
        "<!-- Generert fra config/defaults/setup/*.yaml av tools/gen_setup_guide.py. "
        "Ikke rediger for hånd. -->",
        "",
        "Samme steg som setup-hjelperen på teknikersiden (`/tech` → Oppsett). Hvert steg "
        "sjekkes med helsesjekkene i høyre kolonne og godkjennes av teknikeren.",
        "",
        "| Steg | Sjekkes med | Fiks for meg |",
        "| --- | --- | --- |",
    ]
    for s in steps:
        checks = ", ".join(f"`{c}`" for c in s.checks) or "teknikeren"
        fix = s.fix.label if s.fix else "–"
        out.append(f"| {s.number} {s.title} | {checks} | {fix} |")
    for s in steps:
        out += ["", f"## {s.number}. {s.title}", "", s.why, ""]
        out += [f"{i}. {line}" for i, line in enumerate(s.how, 1)]
        if s.fix:
            out += ["", f"**Fiks for meg:** «{s.fix.label}». {s.fix.confirm}"]
        if s.checks:
            out += ["", "**Sjekk:** " + ", ".join(f"`{c}`" for c in s.checks) + "."]
        else:
            out += ["", "**Sjekk:** teknikeren godkjenner når alt ser riktig ut."]
    return "\n".join(out).rstrip() + "\n"
