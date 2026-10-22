"""HS-7: H-ATEM-2 (the ATEM as approved), H-ATEM-4 (ISO disk) and H-VID-2 (capture format)."""

from __future__ import annotations

from datetime import UTC, datetime

from cutcut.health import FuncCheck
from cutcut.health import checks as hc
from cutcut.health.model import CheckResult


def now() -> datetime:
    return datetime(2026, 10, 22, 9, 0, tzinfo=UTC)


def run(check: FuncCheck) -> CheckResult:
    res = check.fn()
    assert isinstance(res, CheckResult)
    return res


FASIT = {"fasit_input_names": {1: "Camera 1", 2: "Camera 2"}, "fasit_aux": ["program", "input6"]}


def setup(**kw: object) -> CheckResult:
    base: dict[str, object] = {
        "read": True,
        "video_mode": "1080p50",
        "input_names": {1: "Camera 1", 2: "Camera 2"},
        "aux": ["program", "input6"],
        **FASIT,
    }
    return run(hc.atem_setup(lambda: hc.AtemSetupReading(**{**base, **kw}), now))  # type: ignore[arg-type]


def test_H_ATEM_2_as_approved() -> None:
    r = setup()
    assert (r.status, r.value) == ("green", "1080p50")
    assert setup(read=False).status == "green"  # H-ATEM-1 tells the technician already


def test_H_ATEM_2_yellow_when_changed() -> None:
    r = setup(video_mode="1080i50")
    assert r.status == "yellow"
    assert "format 1080i50, ikke 1080p50" in r.message
    r = setup(input_names={1: "Camera 1", 2: "Gjest"}, aux=["program", "input7"])
    assert (r.status, r.value) == ("yellow", "2 avvik")
    assert "AUX 2 viser input7, ikke input6" in r.message


def test_H_ATEM_2_red_when_the_multiview_changed() -> None:
    r = setup(multiview_changed="Rute 3 viser Camera 4, men rutekartet sier Camera 3")
    assert r.status == "red"


def test_H_ATEM_2_without_fasit_says_so() -> None:
    r = setup(fasit_input_names=None, fasit_aux=None)
    assert r.status == "green"
    assert "Ingen ATEM-fasit" in r.message


def iso(**kw: object) -> CheckResult:
    base: dict[str, object] = {
        "read": True,
        "wanted": True,
        "state": "Idle",
        "time_available_s": 5400.0,
        "disk": "ISO-SSD",
        "disk_status": "Active",
    }
    return run(hc.atem_iso(lambda: hc.IsoReading(**{**base, **kw}), now))  # type: ignore[arg-type]


def test_H_ATEM_4() -> None:
    assert (iso().status, iso().value) == ("green", "90 min")
    assert (iso(time_available_s=1800.0).status, iso(time_available_s=1800.0).value) == (
        "yellow",
        "30 min",
    )
    assert iso(disk=None, disk_status=None).status == "red"  # the show is to record ISO
    assert iso(disk=None, disk_status=None, wanted=False).status == "green"
    assert iso(disk_status="Unformatted").value == "disk uformatert"
    assert iso(error="MediaFull").status == "red"
    assert iso(error="DroppingFrames", wanted=False).status == "yellow"


def vid(status: dict[str, object]) -> CheckResult:
    return run(hc.video_format(lambda: status, 1920, 1080, now))


def test_H_VID_2() -> None:
    assert vid({"size": [1920, 1080], "fps": 15}).status == "green"
    assert vid({"size": [1280, 720], "fps": 15}).value == "1280 × 720"
    assert vid({"size": [1920, 1080], "fps": 6}).status == "yellow"
    assert vid({}).status == "green"  # no pictures yet: H-VID-1 says that
