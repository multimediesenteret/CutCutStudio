"""Decision object (spec 5.8). Sent unchanged to log, screens and Companion variables."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from cutcut.common.ids import Mode, RuleId, Shot


class CompanionButton(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page: int = Field(ge=1, le=99)
    row: int = Field(ge=0, le=7)
    col: int = Field(ge=0, le=7)


DecisionAction = Literal["cut", "wait", "hold", "preview"]
"""``cut``, ``wait`` and ``hold`` are from spec 5.8. ``preview`` is added so the log shows
when a candidate went to preview (needed for "preview ≥ 300 ms before program", 10.4)."""


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ts: datetime
    mono_ms: int = Field(default=0, ge=0)
    mode: Mode
    action: DecisionAction
    shot: Shot
    rule: RuleId
    reason: str
    measures: dict[str, float] = Field(default_factory=dict)
    blocked_by: RuleId | None = None
    companion: CompanionButton | None = None
    correlation_id: str = ""
    shadow: bool = False
    switch: str | None = None  # the switch that made it, when it runs in shadow (F-1)
