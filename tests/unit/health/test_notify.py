"""HS-3: email when something is red for over a minute, at once when a recording fails, at most
ten an hour, never in the way of the engine; regi_health for Companion; «Send testvarsel»."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from cutcut.api.app import create_app
from cutcut.app import devices as device_settings
from cutcut.common.clock import FakeClock
from cutcut.common.config import example_site_dir, load_site
from cutcut.common.models.site import AlertsConfig, SmtpConfig
from cutcut.common.store import Store
from cutcut.core.runtime import TICK_MS
from cutcut.health.engine import HealthEvent
from cutcut.health.model import CheckResult
from cutcut.health.notify import Notifier
from cutcut.sim.live import build_live_sim, sim_routes

T0 = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)


class Outbox:
    def __init__(self) -> None:
        self.mails: list[tuple[list[str], str, str]] = []
        self.fail: str | None = None

    def __call__(self, to: list[str], subject: str, body: str) -> None:
        if self.fail:
            raise OSError(self.fail)
        self.mails.append((to, subject, body))

    @property
    def subjects(self) -> list[str]:
        return [s for _, s, _ in self.mails]


class Rig:
    def __init__(self) -> None:
        self.t = 0.0
        self.out = Outbox()
        self.to = ["magnus.lian@ntnu.no"]
        self.n = Notifier(self.out, lambda: self.to, "ntnu-studio", lambda: self.t, lambda: T0)

    def ev(self, kind: str, cid: str, status: str, duration_s: float = 0.0) -> None:
        r = CheckResult(id=cid, status=status, value="", message=f"{cid} er {status}", ts=T0)  # type: ignore[arg-type]
        self.n.on_health(HealthEvent(kind, r, T0, duration_s))  # type: ignore[arg-type]

    def at(self, t: float) -> None:
        self.t = t
        asyncio.run(self.n.tick())


def test_red_for_a_minute_sends_one_mail_and_ok_when_it_closes() -> None:
    r = Rig()
    r.ev("opened", "H-AUD-1", "red")
    r.at(59)
    assert r.out.mails == []
    r.at(60)
    r.at(120)
    assert r.out.subjects == ["[CutCut ntnu-studio] Rødt: H-AUD-1"]
    to, _, body = r.out.mails[0]
    assert to == ["magnus.lian@ntnu.no"]
    assert "Studio: ntnu-studio" in body
    assert "H-AUD-1 er red" in body
    assert "Runbook: docs/runbooks/h-aud-1-ingen-lyd.md" in body
    r.ev("resolved", "H-AUD-1", "green", duration_s=180)
    r.at(200)
    assert r.out.subjects[-1] == "[CutCut ntnu-studio] OK igjen: H-AUD-1"
    assert "etter 3 min" in r.out.mails[-1][2]


def test_short_red_and_yellow_send_nothing() -> None:
    r = Rig()
    r.ev("opened", "H-COMP-1", "red")
    r.at(30)
    r.ev("resolved", "H-COMP-1", "green", 30)
    r.ev("opened", "H-CAM-C2", "yellow")
    r.at(600)
    assert r.out.mails == []


def test_red_that_drops_to_yellow_starts_again() -> None:
    r = Rig()
    r.ev("opened", "H-PRL-1", "red")
    r.at(40)
    r.ev("changed", "H-PRL-1", "yellow")
    r.at(50)
    r.ev("changed", "H-PRL-1", "red")
    r.at(100)
    assert r.out.mails == []  # red again for only 50 s
    r.at(110)
    assert len(r.out.mails) == 1


def test_a_failed_recording_mails_at_once_but_not_twice() -> None:
    r = Rig()
    r.n.on_alert("H-PRL-2", "Opptaket stoppet uten at noen trykket stopp")
    r.at(0)
    r.n.on_alert("H-PRL-2", "Opptaket stoppet uten at noen trykket stopp")
    r.at(60)
    assert r.out.subjects == [
        "[CutCut ntnu-studio] Rødt: Opptaket stoppet uten at noen trykket stopp"
    ]
    r.at(700)
    r.n.on_alert("H-PRL-2", "Opptaket stoppet uten at noen trykket stopp")
    r.at(701)
    assert len(r.out.mails) == 2  # ten minutes later it is news again


def test_at_most_ten_an_hour() -> None:
    r = Rig()
    for i in range(14):
        r.n.on_alert(f"X-{i}", f"feil {i}")
    r.at(0)
    assert len(r.out.mails) == 10
    r.at(1800)
    assert len(r.out.mails) == 10
    r.at(3600)
    assert len(r.out.mails) == 14


def test_a_broken_relay_is_retried_and_reported() -> None:
    r = Rig()
    r.out.fail = "Connection refused"
    r.n.on_alert("H-PRL-1", "Pearl startet ikke opptaket innen 10 s")
    r.at(0)
    assert r.n.last_error == "Connection refused"
    r.out.fail = None
    r.at(30)
    assert r.out.mails == []  # waits a minute before trying again
    r.at(61)
    assert len(r.out.mails) == 1
    assert r.n.last_error is None


def test_nobody_to_tell_keeps_the_mail() -> None:
    r = Rig()
    r.to = []
    r.n.on_alert("H-PRL-1", "Pearl startet ikke")
    r.at(0)
    assert r.out.mails == []
    r.to = ["magnus.lian@ntnu.no"]
    r.at(1)
    assert len(r.out.mails) == 1


def test_addresses_are_checked() -> None:
    assert AlertsConfig(email="magnus.lian@ntnu.no, a@b.no").email == [  # type: ignore[arg-type]
        "magnus.lian@ntnu.no",
        "a@b.no",
    ]
    with pytest.raises(ValidationError, match="ugyldig e-postadresse: magnus"):
        AlertsConfig(email=["magnus"])
    base = load_site(example_site_dir()).devices
    with pytest.raises(device_settings.DeviceSettingsError, match="Ugyldig e-postadresse"):
        device_settings.apply(base, {"alerts.email": "ikke-en-adresse"})
    got = device_settings.apply(base, {"alerts.email": "x@ntnu.no", "alerts.smtp.host": "smtp"})
    assert got.alerts.email == ["x@ntnu.no"]
    assert got.alerts.smtp.host == "smtp"
    assert not any(row["key"].startswith("alerts.") for row in device_settings.rows(base, got, {}))


def test_ntnu_studio_mails_magnus() -> None:
    site = load_site(Path(__file__).parents[3] / "site" / "ntnu-studio")
    assert site.devices.alerts.email == ["magnus.lian@ntnu.no"]


# -- in the studio --------------------------------------------------------------------------


class StudioRig:
    def __init__(self, tmp: Path) -> None:
        self.clock = FakeClock()
        self.store = Store(tmp / "cutcut.db")
        self.mails: list[tuple[SmtpConfig, list[str], str, str]] = []

        def send(cfg: SmtpConfig, to: list[str], subject: str, body: str) -> None:
            if not cfg.host:
                raise OSError("Ingen SMTP-server er satt opp")
            self.mails.append((cfg, to, subject, body))

        self.sim, auth = build_live_sim(self.clock, store=self.store, send_mail=send)
        app = create_app(self.sim.studio, auth, run_loop=False, extra_routes=sim_routes(self.sim))
        self.client = TestClient(app)

    def run(self, seconds: float) -> None:
        studio = self.sim.studio
        for _ in range(int(seconds * 4)):
            for _ in range(250 // TICK_MS):
                self.clock.advance(TICK_MS)
                self.sim.before_tick()
                studio.tick()
            asyncio.run(studio.health.step())
            studio._publish_regi_health()
            if studio.notifier is not None:
                asyncio.run(studio.notifier.tick())


@pytest.fixture
def srig(tmp_path: Path) -> Iterator[StudioRig]:
    r = StudioRig(tmp_path)
    yield r
    r.store.close()


def test_in_the_studio_set_up_test_and_alert(srig: StudioRig) -> None:
    c = srig.client
    info = c.get("/api/settings/alerts").json()
    assert info["enabled"] is False
    assert c.post("/api/settings/alerts/test").status_code == 409  # nobody to send to
    r = c.put(
        "/api/settings/devices",
        json={"alerts.email": "magnus.lian@ntnu.no", "alerts.smtp.host": "smtp.example"},
    )
    assert r.status_code == 200
    assert c.get("/api/settings/alerts").json()["enabled"] is True
    assert c.post("/api/settings/alerts/test").status_code == 200
    cfg, to, subject, _ = srig.mails[-1]
    assert (cfg.host, to, subject) == (
        "smtp.example",
        ["magnus.lian@ntnu.no"],
        "[CutCut example] Testvarsel",
    )
    srig.run(5)
    assert srig.sim.atem.companion_vars["regi_health"] == "ok"
    c.post("/api/sim/fault", json={"kind": "pearl_offline", "on": True})
    srig.run(10)
    assert srig.sim.atem.companion_vars["regi_health"] == "error"
    srig.run(60)
    subjects = [m[2] for m in srig.mails]
    assert "[CutCut example] Rødt: H-PRL-1" in subjects


def test_a_failing_test_mail_says_why(srig: StudioRig) -> None:
    c = srig.client
    c.put("/api/settings/devices", json={"alerts.email": "magnus.lian@ntnu.no"})
    r = c.post("/api/settings/alerts/test")
    assert r.status_code == 409
    assert "SMTP" in r.json()["detail"]
    assert c.get("/api/settings/alerts").json()["last_error"] == "Ingen SMTP-server er satt opp"
    srig.run(1)
    checks = {x["id"]: x for x in srig.client.get("/api/health/checks").json()}
    assert checks["H-VARSEL-1"]["status"] == "yellow"
