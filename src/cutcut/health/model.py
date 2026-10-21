"""What a health check reports (spec 8.5, docs/plans/setup-health.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Status = Literal["green", "yellow", "red"]
CheckLevel = Literal["connected", "working", "as_agreed"]  # the three levels in 8.5

RANK: dict[Status, int] = {"green": 0, "yellow": 1, "red": 2}


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str  # "H-AUD-1"
    status: Status
    value: str  # what was found, short: "12 ms", "ikke tilkoblet"
    expected: str | None = None  # what it should be, when there is a fasit
    message: str  # one Norwegian sentence for the technician
    ts: datetime
    level: CheckLevel = "connected"
    for_user: bool = False  # red is also shown on the touch screen («trykk Hjelp»)
    since: datetime | None = None  # when the current problem started (open issue)
