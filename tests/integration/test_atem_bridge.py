"""DA-1/DA-2 contract: core reads exactly what the Node bridge sends (tests/fixtures/atem)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cutcut.common.config import load_site
from cutcut.common.ids import SourceId
from cutcut.core.intents import DirectCut, ShowAudioOnly, Take
from cutcut.devices.atem.bridge import STALE_S, AtemBridgeClient, input_map
from cutcut.devices.companion.executor import CompanionExecutor
from cutcut.setup.multiview import check_readback

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "atem" / "state-studio.json").read_text())
SITE = load_site(ROOT / "site" / "multimediesenteret")
SHOW = SITE.shows["panel-4"]


@dataclass
class Clock:
    t: float = 10.0

    def __call__(self) -> float:
        return self.t


@dataclass
class Bus:
    sent: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def __call__(self, topic: str, payload: dict[str, Any]) -> None:
        self.sent.append((topic, payload))


def client() -> tuple[AtemBridgeClient, Bus, Clock]:
    bus, clock = Bus(), Clock()
    c = AtemBridgeClient(bus, input_map(SHOW), clock)
    return c, bus, clock


def test_input_map_follows_the_studio_D054() -> None:
    m = input_map(SHOW)
    assert m[1] is SourceId.C1
    assert m[4] is SourceId.C4
    assert m[6] is SourceId.C5  # overview / bird's-eye
    assert m[7] is SourceId.LAPTOP
    assert m[6000] is SourceId.SUPERSOURCE


def test_bridge_state_becomes_readback() -> None:
    c, _, _ = client()
    assert c.readback() is None
    c.on_message("atem.state", FIXTURE)
    rb = c.readback()
    assert rb is not None
    assert rb.program is SourceId.SUPERSOURCE
    assert rb.program_layout == "AUDIO_ONLY"  # media player 1 is on program in the photo
    assert rb.preview is SourceId.C1
    assert c.status().model == "TelevisionStudioHD8ISO"


def test_stale_or_disconnected_bridge_means_no_readback_I1() -> None:
    c, _, clock = client()
    c.on_message("atem.state", FIXTURE)
    clock.t += STALE_S + 0.1
    assert c.readback() is None
    clock.t -= STALE_S
    c.on_message("atem.status", {"connected": False, "last_error": "frakoblet"})
    assert c.readback() is None


def test_multiview_from_the_bridge_is_checked() -> None:
    c, _, _ = client()
    c.on_message("atem.state", FIXTURE)
    mv = c.multiview_readback()
    assert mv is not None
    assert SITE.multiview is not None
    findings = {(f.check, f.level) for f in check_readback(SITE.multiview, mv)}
    # As in the photo: safe area on; the status window is not a source CutCut reads.
    assert ("H-MV-6", "warn") in findings
    assert ("H-MV-5", "warn") in findings
    assert not any(level == "error" for _, level in findings)


def test_direct_cut_and_audio_only_go_out_as_commands() -> None:
    c, bus, _ = client()
    c.on_message("atem.state", FIXTURE)
    c.submit(DirectCut(SourceId.C5))
    c.submit(ShowAudioOnly())
    assert [p["args"]["input"] for _, p in bus.sent] == [6, 3010]
    assert all(t == "atem.cmd" for t, _ in bus.sent)
    c.on_message("atem.ack", {"id": bus.sent[0][1]["id"], "ok": False, "error": "busy"})
    assert c.status().failed == 1


def test_no_commands_while_the_atem_is_not_readable() -> None:
    c, bus, _ = client()
    c.submit(DirectCut(SourceId.C2))
    assert bus.sent == []
    assert "ikke tilkoblet" in (c.status().last_error or "")


def test_S5_companion_down_cuts_through_the_bridge() -> None:
    """End to end on the reserve path: Companion executor → bridge client → atem.cmd."""
    from cutcut.common.config import example_site_dir
    from cutcut.core.intents import SetPreview
    from cutcut.devices.companion.client import CompanionError

    class DeadCompanion:
        def press(self, page: int, row: int, col: int) -> None:
            raise CompanionError("borte")

        def set_var(self, name: str, value: str) -> None:
            raise CompanionError("borte")

    c, bus, clock = client()
    c.on_message("atem.state", FIXTURE)
    cmap = load_site(example_site_dir()).companion_map
    ex = CompanionExecutor(DeadCompanion(), cmap, fallback=c, start_thread=False, clock=clock)
    for _ in range(3):
        ex.submit(SetPreview(SourceId.C2))
        ex.step()
    ex.submit(SetPreview(SourceId.C3))
    ex.submit(Take("cut"))
    assert bus.sent[-1] == (
        "atem.cmd",
        {"id": bus.sent[-1][1]["id"], "op": "cut", "args": {"input": 3}},
    )
