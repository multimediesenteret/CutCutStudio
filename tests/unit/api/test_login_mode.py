"""D-057: «Start uten kort» until the card reader and the NTNU API are switched on."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cutcut.app.studio import Studio, StudioDeps
from tests.unit.api.test_api import TEST_CARD, Rig


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def test_the_studio_starts_with_the_start_button_the_simulator_with_cards(rig: Rig) -> None:
    sim_deps = rig.sim.studio.deps
    studio = Studio(StudioDeps(**{**sim_deps.__dict__, "simulator": False, "store": None}))
    assert studio.login_mode == "open"
    assert rig.state()["touch"]["login"] == "card"


def test_start_without_card_logs_in_a_guest(rig: Rig) -> None:
    c = rig.client
    assert c.put("/api/settings/login", json={"mode": "open"}).status_code == 200
    rig.run(100)
    assert rig.state()["touch"]["login"] == "open"
    assert c.post("/api/touch/start").status_code == 200
    rig.run(100)
    s = rig.state()
    assert s["touch"]["step"] == "ready"
    assert s["session"]["user"] == {"username": "gjest", "display_name": "Gjest"}
    # The rest of the flow is the same as with a card.
    assert c.put("/api/session/show", json={"guests": 1, "video": True}).status_code == 200
    assert c.post("/api/recording", json={"action": "start"}).status_code == 200
    rig.run(5000)
    assert rig.state()["touch"]["step"] == "rec"


def test_card_mode_refuses_the_button_but_takes_cards(rig: Rig) -> None:
    c = rig.client
    r = c.post("/api/touch/start")
    assert r.status_code == 409
    assert "NTNU-kortet" in r.json()["detail"]
    c.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(100)
    assert rig.state()["session"]["user"]["display_name"] == "Testkort A"


def test_cards_still_work_in_open_mode(rig: Rig) -> None:
    rig.client.put("/api/settings/login", json={"mode": "open"})
    rig.client.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(100)
    assert rig.state()["session"]["user"]["display_name"] == "Testkort A"


def test_only_admin_changes_it_and_it_survives_a_restart(tmp_path: Path) -> None:
    r = Rig(tmp_path, dev_admin=False)
    try:
        assert r.client.put("/api/settings/login", json={"mode": "open"}).status_code in (401, 403)
        assert r.client.put("/api/settings/login", json={"mode": "x"}).status_code == 422
        r.sim.studio.set_login_mode("open", "admin", "test")
    finally:
        r.store.close()
    again = Rig(tmp_path)
    try:
        assert again.sim.studio.login_mode == "open"
    finally:
        again.store.close()
