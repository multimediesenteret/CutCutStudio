"""P10: the bridge tells «something else on air» from «the ATEM cannot be read»."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cutcut.common.ids import AUDIO_ONLY, SourceId
from cutcut.devices.atem.bridge import STALE_S, AtemBridgeClient

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "atem" / "state-studio.json"
STATE: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
INPUTS = {1: SourceId.C1, 2: SourceId.C2, 6: SourceId.C5, 7: SourceId.LAPTOP}


def client(program: int, preview: int = 1, t: list[float] | None = None) -> AtemBridgeClient:
    clock = t if t is not None else [0.0]
    c = AtemBridgeClient(send=lambda *_: None, inputs=dict(INPUTS), clock=lambda: clock[0])
    c.on_message("atem.state", {**STATE, "program_input": program, "preview_input": preview})
    return c


@pytest.mark.parametrize(
    "program", [0, 1000, 2001, 3020], ids=["svart", "fargebarer", "farge 1", "mediaspiller 2"]
)
def test_an_unknown_source_on_program_is_other_not_unreadable(program: int) -> None:
    rb = client(program).readback()
    assert rb is not None
    assert rb.program is SourceId.OTHER
    assert rb.program_input == program
    assert rb.preview is SourceId.C1


def test_media_player_1_is_the_audio_only_graphic() -> None:
    rb = client(3010).readback()
    assert rb is not None
    assert rb.program is SourceId.SUPERSOURCE
    assert rb.program_layout == AUDIO_ONLY


def test_a_camera_is_a_camera() -> None:
    rb = client(2, preview=0).readback()
    assert rb is not None
    assert rb.program is SourceId.C2
    assert rb.preview is SourceId.OTHER


def test_old_state_is_unreadable() -> None:
    t = [0.0]
    c = client(1, t=t)
    t[0] = STALE_S + 0.1
    assert c.readback() is None
