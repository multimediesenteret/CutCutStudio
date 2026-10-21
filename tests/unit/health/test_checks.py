"""HS-2: each check in green, yellow and red, and the checks in the simulator."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cutcut.common.platform.system import SystemSnapshot
from cutcut.health import FuncCheck
from cutcut.health import checks as hc
from tests.unit.api.test_api import Rig


def now() -> datetime:
    return datetime(2026, 10, 21, 8, 0, tzinfo=UTC)


def run(check: FuncCheck) -> tuple[str, str]:
    r = asyncio.run(check.run())
    return r.status, r.value


def snap(**kw: float) -> SystemSnapshot:
    base = {
        "cpu_percent": 10.0,
        "memory_percent": 40.0,
        "disk_free_gb": 300.0,
        "disk_free_percent": 70.0,
        "uptime_s": 100.0,
        "process_rss_mb": 100.0,
    }
    return SystemSnapshot(**{**base, **kw})


@pytest.mark.parametrize(
    ("reading", "status"),
    [
        (None, "yellow"),
        (hc.ProcessReading("core", True), "green"),
        (hc.ProcessReading("core", False, 1, "avsluttet med kode 1"), "yellow"),
        (hc.ProcessReading("core", True, 5), "green"),
        (hc.ProcessReading("core", True, 6), "yellow"),
    ],
)
def test_H_PROC(reading: hc.ProcessReading | None, status: str) -> None:
    assert run(hc.process("core", lambda: reading, now))[0] == status


def test_H_PROC_supervisor() -> None:
    assert run(hc.supervisor(lambda: 2_000, now))[0] == "green"
    assert run(hc.supervisor(lambda: 12_000, now)) == ("yellow", "12 s siden")


@pytest.mark.parametrize(
    ("kw", "cid", "status"),
    [
        ({}, "H-PC-1", "green"),
        ({"disk_free_gb": 10.0}, "H-PC-1", "yellow"),
        ({"disk_free_gb": 1.0}, "H-PC-1", "red"),
        ({"memory_percent": 95.0}, "H-PC-2", "yellow"),
        ({"cpu_percent": 90.0}, "H-PC-3", "yellow"),
        ({"cpu_percent": 50.0}, "H-PC-3", "green"),
    ],
)
def test_H_PC(kw: dict[str, float], cid: str, status: str) -> None:
    checks = {c.id: c for c in hc.pc(lambda: snap(**kw), now)}
    assert run(checks[cid])[0] == status


GB = 1_000_000_000


@pytest.mark.parametrize(
    ("reading", "status", "for_user"),
    [
        (hc.PearlReading(online=False), "red", True),
        (hc.PearlReading(online=True, free_bytes=500 * GB), "green", False),
        (hc.PearlReading(online=True, free_bytes=5 * GB), "yellow", False),  # ~33 min
        (hc.PearlReading(online=True, free_bytes=1 * GB), "red", True),  # ~6 min
        (hc.PearlReading(online=True, error="Kein Signal"), "yellow", False),
        (hc.PearlReading(online=True), "green", False),
    ],
)
def test_H_PRL_1(reading: hc.PearlReading, status: str, for_user: bool) -> None:
    r = asyncio.run(hc.pearl(lambda: reading, now).run())
    assert (r.status, r.for_user) == (status, for_user)


def test_storage_minutes_assume_20_mbps() -> None:
    assert hc.storage_minutes(9 * GB) == 60


@pytest.mark.parametrize(
    ("connected", "uptime", "status"), [(True, 0, "green"), (False, 5, "green"), (False, 20, "red")]
)
def test_H_ATEM_1(connected: bool, uptime: float, status: str) -> None:
    assert run(hc.atem(lambda: connected, lambda: uptime, now))[0] == status


@pytest.mark.parametrize(
    ("reading", "status", "value"),
    [
        (hc.CompanionReading(True, 1, pages_read=True), "green", "sider v1"),
        (hc.CompanionReading(True, None, pages_read=True), "red", "ingen CutCut-sider"),
        (hc.CompanionReading(True, 2, pages_read=True), "red", "sider v2"),
        (hc.CompanionReading(False, error="ConnectError"), "red", "svarer ikke"),
        (hc.CompanionReading(True), "green", "svarer"),  # simulator: nothing to read
    ],
)
def test_H_COMP_1(reading: hc.CompanionReading, status: str, value: str) -> None:
    assert run(hc.companion(lambda: reading, 1, now)) == (status, value)


# -- in the simulator ---------------------------------------------------------------------------


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def settle(rig: Rig, seconds: float) -> dict[str, str]:
    for _ in range(int(seconds * 4)):
        rig.run(250)
        asyncio.run(rig.sim.studio.health.step())
    return {c["id"]: c["status"] for c in rig.state()["health"]["checks"]}


def test_the_simulator_is_all_green(rig: Rig) -> None:
    got = settle(rig, 20)
    want = {"H-AUD-1", "H-PRL-1", "H-ATEM-1", "H-COMP-1", "H-PC-1", "H-PC-2", "H-PC-3"}
    assert set(got) == want
    assert set(got.values()) == {"green"}


@pytest.mark.parametrize(
    ("fault", "cid", "status", "blocks_user"),
    [
        ("pearl_offline", "H-PRL-1", "red", True),
        ("atem_down", "H-ATEM-1", "red", True),
        ("companion_down", "H-COMP-1", "red", False),
        ("disk_full", "H-PC-1", "red", False),
    ],
)
def test_faults_turn_their_check_red(
    rig: Rig, fault: str, cid: str, status: str, blocks_user: bool
) -> None:
    settle(rig, 20)
    rig.client.post("/api/sim/fault", json={"kind": fault, "on": True})
    got = settle(rig, 31)  # the PC checks run every 30 s
    assert got[cid] == status
    checks = rig.state()["health"]["checks"]
    assert any(c["for_user"] and c["status"] == "red" for c in checks) is blocks_user
    assert rig.client.get("/api/health").json()["status"] == "error"

    rig.client.post("/api/sim/fault", json={"kind": fault, "on": False})
    got = settle(rig, 31)
    assert got[cid] == "green"  # the live check is green; the issue still waits out 30 s
    assert not any(c["for_user"] and c["status"] == "red" for c in rig.state()["health"]["checks"])
    settle(rig, 31)
    assert rig.state()["health"]["status"] == "green"


def test_H_AUD_1_says_why_when_audio_capture_knows() -> None:
    check = hc.audio_stream(
        lambda: 5_000, now, lambda: {"last_error": "fant ikke «RODECaster» med 20 kanaler på ASIO"}
    )
    r = asyncio.run(check.run())
    assert r.status == "red"
    assert "fant ikke «RODECaster»" in r.message


def test_touch_heartbeat_and_H_PROC_touch(rig: Rig) -> None:
    """SO-6: the touch screen beats every 5 s; the kiosk guard and H-PROC-touch read it."""
    c = rig.client
    assert c.get("/api/touch/heartbeat").json() == {"age_ms": None}
    got = settle(rig, 2)
    assert "H-PROC-touch" not in got  # no touch screen yet (e.g. development): no check
    assert c.post("/api/touch/heartbeat").status_code == 200
    got = settle(rig, 6)
    assert got["H-PROC-touch"] == "green"
    assert c.get("/api/touch/heartbeat").json()["age_ms"] >= 5000
    got = settle(rig, 30)  # Edge hung: no more beats
    assert got["H-PROC-touch"] == "yellow"
    c.post("/api/touch/heartbeat")
    assert settle(rig, 6)["H-PROC-touch"] == "green"
