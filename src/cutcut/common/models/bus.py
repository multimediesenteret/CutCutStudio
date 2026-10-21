"""Envelope for messages on the internal bus (ZeroMQ, spec 3; docs/plans/common.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

BUS_SCHEMA_VERSION = 1


class BusMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    topic: str = Field(pattern=r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")
    source: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")  # process name, e.g. "audio-capture"
    ts: datetime
    mono_ms: int = Field(ge=0)
    seq: int = Field(ge=0)
    schema_version: int = BUS_SCHEMA_VERSION
    payload: dict[str, Any] = Field(default_factory=dict)
