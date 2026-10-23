"""D-071: the multiview capture method (INOGENI or the ATEM's webcam output) and the camera
model are chosen on the setup screen; the video layer and the engine follow without a restart."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from cutcut.common.ids import CameraId
from cutcut.common.models.site import CAPTURE_DELAY_MS, VideoDevice
from cutcut.vision.capture import OpenCvSource
from tests.unit.api.test_api import Rig


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def video(rig: Rig) -> dict[str, Any]:
    out: dict[str, Any] = rig.client.get("/api/settings/devices").json()["video"]
    return out


def test_inogeni_is_the_default_and_both_methods_are_offered(rig: Rig) -> None:
    v = video(rig)
    assert v["method"] == "inogeni"
    assert v["name_used"] == "INOGENI"
    assert [m["value"] for m in v["methods"]] == ["inogeni", "atem_usb"]
    assert v["delay_ms"] == CAPTURE_DELAY_MS["inogeni"]
    assert v["measured"] is False
    assert rig.sim.studio.engine.config.vision_delay_ms == CAPTURE_DELAY_MS["inogeni"]


def test_choosing_the_atem_webcam_output_reaches_the_video_layer_and_the_engine(
    rig: Rig,
) -> None:
    sent: list[dict[str, Any]] = []
    rig.sim.studio.on_vision_source = sent.append
    r = rig.client.put("/api/settings/devices", json={"video.method": "atem_usb"})
    assert r.status_code == 200
    v = r.json()["video"]
    assert v["method"] == "atem_usb"
    assert v["method_overridden"] is True
    assert v["name_used"] == "Blackmagic Design"
    assert sent[-1] == {
        "method": "atem_usb",
        "name": "Blackmagic Design",
        "delay_ms": CAPTURE_DELAY_MS["atem_usb"],
    }
    assert rig.sim.studio.engine.config.vision_delay_ms == CAPTURE_DELAY_MS["atem_usb"]
    # A measured delay (hwtest vision V4) wins over the starting point, per method.
    r = rig.client.put("/api/settings/devices", json={"video.delay_ms.atem_usb": "95"})
    v = r.json()["video"]
    assert v["delay_ms"] == 95
    assert v["measured"] is True
    assert rig.sim.studio.engine.config.vision_delay_ms == 95
    # Back to INOGENI: its own (unmeasured) starting point, not the ATEM's number.
    rig.client.put("/api/settings/devices", json={"video.method": None})
    assert rig.sim.studio.engine.config.vision_delay_ms == CAPTURE_DELAY_MS["inogeni"]
    assert "video" in rig.client.get("/api/settings/devices.yaml").text


def test_a_name_can_be_given_when_windows_calls_the_device_something_else(rig: Rig) -> None:
    r = rig.client.put(
        "/api/settings/devices", json={"video.method": "atem_usb", "video.name": "ATEM USB"}
    )
    assert r.json()["video"]["name_used"] == "ATEM USB"


def test_bad_capture_settings_are_refused(rig: Rig) -> None:
    bad = rig.client.put("/api/settings/devices", json={"video.method": "decklink"})
    assert bad.status_code == 409
    assert "INOGENI" in bad.json()["detail"]
    bad = rig.client.put("/api/settings/devices", json={"video.delay_ms.inogeni": "-5"})
    assert bad.status_code == 409
    assert "millisekunder" in bad.json()["detail"]
    assert video(rig)["method"] == "inogeni"


def test_the_camera_model_is_a_choice_per_camera_D070(rig: Rig) -> None:
    rows = {x["key"]: x for x in rig.client.get("/api/settings/devices").json()["rows"]}
    c2 = rows["cameras.C2.ip"]
    assert c2["model_key"] == "cameras.C2.model"
    assert {"OBSBOT Tail 2", "Canon CR-N300"} <= set(c2["model_options"])
    r = rig.client.put("/api/settings/devices", json={"cameras.C2.model": "Canon CR-N300"})
    assert r.status_code == 200
    rows = {x["key"]: x for x in r.json()["rows"]}
    assert rows["cameras.C2.ip"]["model"] == "Canon CR-N300"
    assert rows["cameras.C2.ip"]["model_overridden"] is True
    assert rig.sim.studio.devices.cameras[CameraId.C2].model == "Canon CR-N300"
    bad = rig.client.put("/api/settings/devices", json={"cameras.C2.model": "Sony"})
    assert bad.status_code == 409
    assert "kameramodell" in bad.json()["detail"]


def test_the_video_device_names_by_method() -> None:
    assert VideoDevice().device_name == "INOGENI"
    assert VideoDevice(method="atem_usb").device_name == "Blackmagic Design"
    assert VideoDevice(method="atem_usb", name=" Min ATEM ").device_name == "Min ATEM"
    assert VideoDevice(delay_ms={"atem_usb": 90}).expected_delay_ms == CAPTURE_DELAY_MS["inogeni"]


class FakeCap:
    def __init__(self, index: int) -> None:
        self.index = index
        self.released = False

    def isOpened(self) -> bool:
        return True

    def set(self, *_: Any) -> None:
        pass

    def read(self) -> tuple[bool, Any]:
        return True, object()

    def release(self) -> None:
        self.released = True


class FakeCv2:
    CAP_DSHOW = CAP_ANY = 0
    CAP_PROP_FRAME_WIDTH = CAP_PROP_FRAME_HEIGHT = CAP_PROP_FPS = 0

    def __init__(self) -> None:
        self.caps: list[FakeCap] = []

    def VideoCapture(self, index: int, _api: int = 0) -> FakeCap:
        self.caps.append(FakeCap(index))
        return self.caps[-1]


def test_the_video_layer_switches_device_without_a_restart() -> None:
    cv2 = FakeCv2()
    devices = ["Integrated Camera", "INOGENI 4KXUSB3", "Blackmagic Design"]
    src = OpenCvSource(0, device_name="INOGENI", list_devices=lambda: devices, cv2=cv2)
    assert src.read() is not None
    assert cv2.caps[-1].index == 1
    assert src.use_device("Blackmagic Design") is True
    assert cv2.caps[0].released
    assert src.read() is not None
    assert cv2.caps[-1].index == 2
    assert src.found_as == "Blackmagic Design"
    assert src.use_device("Blackmagic Design") is False  # the same: nothing happens
    assert OpenCvSource(str(Path("x.mp4"))).use_device("INOGENI") is False
