"""P1 (D-062–D-065): the studio PC. The DeckLink card is found by name, the video layer is
started by the supervisor, both network cards are checked, the support e-mail reaches touch,
and live text and turn prediction are gone without breaking saved settings."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from cutcut.common.config import example_site_dir
from cutcut.common.models.show import Features
from cutcut.common.platform.system import FakeSystem, NetInterface
from cutcut.health import checks
from cutcut.health.model import CheckResult
from cutcut.supervisor.main import SupervisorOptions, specs
from cutcut.vision.capture import OpenCvSource, find_device
from tests.unit.api.test_api import Rig

T0 = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
DSHOW = ["OBS Virtual Camera", "Decklink Video Capture", "Blackmagic WDM Capture"]


class FakeCap:
    def __init__(self, index: int) -> None:
        self.index = index
        self.props: dict[int, float] = {}

    def isOpened(self) -> bool:
        return True

    def set(self, prop: int, value: float) -> None:
        self.props[prop] = value

    def read(self) -> tuple[bool, Any]:
        return False, None

    def release(self) -> None:
        pass


class FakeCv2:
    CAP_DSHOW = 700
    CAP_ANY = 0
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4
    CAP_PROP_FPS = 5

    def __init__(self) -> None:
        self.opened: list[FakeCap] = []

    def VideoCapture(self, index: int, api: int = 0) -> FakeCap:
        cap = FakeCap(index)
        self.opened.append(cap)
        return cap


def test_the_decklink_is_found_by_name() -> None:
    assert find_device("DeckLink", DSHOW) == 1
    assert find_device("decklink", DSHOW) == 1
    assert find_device("INOGENI", DSHOW) is None
    cv2 = FakeCv2()
    src = OpenCvSource(0, device_name="DeckLink", list_devices=lambda: DSHOW, cv2=cv2)
    src.read()
    assert cv2.opened[0].index == 1
    assert src.found_as == "Decklink Video Capture"
    assert cv2.opened[0].props[FakeCv2.CAP_PROP_FPS] == 50
    # no card with that name: the number from devices.yaml
    cv2 = FakeCv2()
    src = OpenCvSource(2, device_name="DeckLink", list_devices=lambda: ["Webcam"], cv2=cv2)
    src.read()
    assert cv2.opened[0].index == 2


def test_the_supervisor_starts_the_video_layer(tmp_path: Path) -> None:
    pytest.importorskip("cv2")
    names = [s.name for s in specs(SupervisorOptions(example_site_dir(), tmp_path))]
    assert names == ["core", "atem-bridge", "audio-capture", "vision"]


def nics(*items: tuple[str, bool, tuple[str, ...]]) -> FakeSystem:
    s = FakeSystem()
    s.nics = [NetInterface(n, up, ips) for n, up, ips in items]
    return s


def run_net(system: FakeSystem) -> dict[str, Any]:
    out = {}
    for c in checks.network(system.interfaces, lambda: "10.10.10.10", lambda: T0):
        r = c.fn()
        assert isinstance(r, CheckResult)
        out[r.id] = r
    return out


def test_two_network_cards() -> None:
    ok = run_net(FakeSystem())
    assert ok["H-NET-1"].status == "green"
    assert ok["H-NET-2"].status == "green"
    only_campus = run_net(nics(("Campus", True, ("192.168.50.20",))))
    assert only_campus["H-NET-1"].status == "red"
    assert "studio-switchen" in only_campus["H-NET-1"].message
    unplugged = run_net(nics(("Studio", False, ("10.10.10.2",)), ("Campus", True, ("172.16.1.5",))))
    assert unplugged["H-NET-1"].status == "red"
    no_way_out = run_net(nics(("Studio", True, ("10.10.10.2",)), ("APIPA", True, ("169.254.3.4",))))
    assert no_way_out["H-NET-1"].status == "green"
    assert no_way_out["H-NET-2"].status == "yellow"


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def test_support_email_reaches_touch_and_can_be_changed(rig: Rig) -> None:
    c = rig.client
    assert rig.state()["studio"]["support_email"] == "magnus.lian@ntnu.no"
    assert c.get("/api/settings/alerts").json()["support_email"] == "magnus.lian@ntnu.no"
    r = c.put("/api/settings/devices", json={"support.email": "ikke-en-adresse"})
    assert r.status_code == 409
    assert "e-postadresse" in r.json()["detail"]
    assert (
        c.put("/api/settings/devices", json={"support.email": "hjelp@example.org"}).status_code
        == 200
    )
    assert rig.state()["studio"]["support_email"] == "hjelp@example.org"
    c.put("/api/settings/devices", json={"support.email": None})  # back to the default
    assert rig.state()["studio"]["support_email"] == "magnus.lian@ntnu.no"


def test_retired_switches_load_from_old_settings() -> None:
    f = Features.model_validate({"bird": True, "live_transcript": True, "turn_prediction": False})
    assert "live_transcript" not in f.model_dump()
    with pytest.raises(ValueError, match="extra"):
        Features.model_validate({"telepathy": True})
