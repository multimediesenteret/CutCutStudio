"""Setup entered in the app, not in the repository: technicians, «Lagre oppsett» and
«Hent oppsett», and the automatic copy on the PC."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import HTTPException

from cutcut.api.auth import Auth
from cutcut.app import setup_file
from cutcut.app.studio import CommandError
from cutcut.common.models.site import Staff
from cutcut.common.platform.secrets import FakeSecretStore
from tests.unit.api.test_api import Rig


def secret_keys(data: object) -> list[str]:
    if isinstance(data, dict):
        found = [k for k in data if any(w in str(k).lower() for w in ("pin", "password", "key"))]
        return found + [x for v in data.values() for x in secret_keys(v)]
    if isinstance(data, list):
        return [x for v in data for x in secret_keys(v)]
    return []


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def test_technicians_are_kept_in_the_app_and_survive_a_restart(tmp_path: Path) -> None:
    r = Rig(tmp_path)
    c = r.client
    assert c.get("/api/settings/staff").json()["admins"] == ["admin1"]  # staff.yaml to start
    got = c.put("/api/settings/staff", json={"operators": ["kari"], "admins": ["ola"]})
    assert got.status_code == 200
    assert got.json() == {"operators": ["kari"], "admins": ["ola"], "first_setup": False}
    assert r.auth.staff.role_of("ola") == "admin"  # sign-in follows at once
    assert r.auth.staff.role_of("tekniker1") is None
    r.store.flush()
    r.store.close()
    again = Rig(tmp_path)
    assert again.client.get("/api/settings/staff").json()["operators"] == ["kari"]
    assert again.auth.staff.role_of("kari") == "operator"
    again.store.close()


def test_nobody_locks_themselves_out(rig: Rig) -> None:
    c = rig.client
    r = c.put("/api/settings/staff", json={"operators": ["kari"], "admins": []})
    assert r.status_code == 409
    assert "Minst én må være admin" in r.json()["detail"]
    r = c.put("/api/settings/staff", json={"operators": [], "admins": ["kari ola"]})
    assert r.status_code == 409
    assert "ugyldig brukernavn" in r.json()["detail"]


def test_an_admin_must_keep_admin(rig: Rig) -> None:
    studio = rig.sim.studio
    with pytest.raises(CommandError, match="låser du deg ute"):
        studio.check_staff(["kari"], ["ola"], actor="kari")
    assert studio.check_staff([], ["kari"], actor="kari").admins == ["kari"]


def test_first_setup_lets_the_admin_pin_in() -> None:
    secrets = FakeSecretStore({"admin_pin": "9999", "operator_pin": "1111"})
    auth = Auth(Staff(), secrets)
    _, who = auth.sign_in("hvemsomhelst", "9999")
    assert (who.role, who.actor) == ("admin", "hvemsomhelst")
    with pytest.raises(HTTPException):
        auth.sign_in("hvemsomhelst", "1111")  # the operator PIN is not enough
    auth.staff = Staff(admins=["ola"])
    with pytest.raises(HTTPException, match="teknikerlisten"):
        auth.sign_in("hvemsomhelst", "9999")


def test_save_and_bring_back_the_setup(rig: Rig) -> None:
    c = rig.client
    c.put("/api/settings/devices", json={"cameras.C2.ip": "10.20.0.22", "alerts.email": "a@b.no"})
    c.put("/api/settings/staff", json={"operators": ["kari"], "admins": ["ola", "simulator"]})
    c.put("/api/settings/login", json={"mode": "open"})
    r = c.get("/api/settings/setup.yaml")
    assert r.status_code == 200
    assert 'filename="cutcut-oppsett-example-' in r.headers["content-disposition"]
    text = r.text
    assert "kind: cutcut-oppsett" in text
    assert "10.20.0.22" in text
    assert not secret_keys(setup_file.parse(text).model_dump())  # no PINs or passwords

    # someone changes things, then the saved file is brought back
    c.put("/api/settings/devices", json={"cameras.C2.ip": "10.30.0.22", "alerts.email": None})
    c.put("/api/settings/staff", json={"operators": [], "admins": ["simulator"]})
    check = c.post("/api/settings/setup/check", json={"text": text})
    assert check.status_code == 200
    summary = " | ".join(check.json()["changes"])
    assert "Utstyr og varsling: 2 endret" in summary
    assert "Teknikere: 1 operatører, 2 admin" in summary
    ip = c.get("/api/settings/devices").json()["rows"]
    assert next(x for x in ip if x["key"] == "cameras.C2.ip")["value"] == "10.30.0.22"  # unchanged

    assert c.post("/api/settings/setup/import", json={"text": text}).status_code == 200
    rows = c.get("/api/settings/devices").json()["rows"]
    assert next(x for x in rows if x["key"] == "cameras.C2.ip")["value"] == "10.20.0.22"
    assert c.get("/api/settings/alerts").json()["email"] == ["a@b.no"]
    assert c.get("/api/settings/staff").json()["operators"] == ["kari"]
    assert any(a["code"] == "OPPSETT" for a in rig.state()["alerts"])


def test_a_bad_file_changes_nothing(rig: Rig) -> None:
    c = rig.client
    before = c.get("/api/settings/devices").json()
    r = c.post("/api/settings/setup/import", json={"text": "hei: på deg"})
    assert r.status_code == 409
    assert "ikke en oppsettfil" in r.json()["detail"]
    bad = "kind: cutcut-oppsett\nstudio: example\ndevices: {cameras.C2.ip: '999.1.1.1'}\n"
    bad += "staff: {operators: [kari], admins: [simulator]}\n"
    r = c.post("/api/settings/setup/import", json={"text": bad})
    assert r.status_code == 409
    assert "IP" in r.json()["detail"]
    assert c.get("/api/settings/devices").json() == before
    assert c.get("/api/settings/staff").json()["operators"] == ["tekniker1", "tekniker2"]


def test_only_admins(tmp_path: Path) -> None:
    r = Rig(tmp_path, dev_admin=False)
    try:
        for method, path in (
            ("GET", "/api/settings/staff"),
            ("GET", "/api/settings/setup.yaml"),
            ("POST", "/api/settings/setup/import"),
        ):
            got = r.client.request(method, path, json={"text": ""})
            assert got.status_code in (401, 403), path
    finally:
        r.store.close()


def test_a_copy_is_kept_on_the_pc(tmp_path: Path) -> None:
    setup = setup_file.SetupFile(studio="studio", devices={"atem.ip": "10.0.0.1"})
    folder = tmp_path / "oppsett"
    for minute in range(25):
        setup_file.autosave(folder, setup, datetime(2026, 10, 22, 12, minute, tzinfo=UTC))
    copies = sorted(folder.glob("cutcut-oppsett-*.yaml"))
    assert len(copies) == setup_file.KEEP
    assert copies[0].name == "cutcut-oppsett-studio-20261022-120500.yaml"
    latest = (folder / setup_file.LATEST).read_text(encoding="utf-8")
    assert setup_file.parse(latest).devices == {"atem.ip": "10.0.0.1"}
