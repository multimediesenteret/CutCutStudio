"""AU-7: setup step 5 – right channel, leakage and noise floor, saved as fasit."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cutcut.audio.analyzer import Analyzer
from cutcut.audio.main import apply_config
from cutcut.common.config import load_site
from cutcut.common.ids import MicId
from cutcut.common.models.baseline import Baseline
from cutcut.setup.mic_check import NOISE_MS, TALK_MS, MicCheck, write_baseline
from tests.unit.api.test_api import TEST_CARD, Rig

M1, M2, M3 = MicId.M1, MicId.M2, MicId.M3
ROOT = Path(__file__).resolve().parents[3]


def talk(check: MicCheck, levels: dict[MicId, float], ms: int = TALK_MS, start: int = 0) -> None:
    for t in range(start, start + ms + 10, 10):
        check.feed(levels, t)


def test_one_person_talking_gives_the_right_channel_and_the_leakage() -> None:
    check = MicCheck([M1, M2, M3])
    check.start_talk(M1, 0)
    talk(check, {M1: -18.0, M2: -40.0, M3: -44.0})
    r = check.results[M1]
    assert r.right_channel
    assert r.leak_db == {M2: -22.0, M3: -26.0}
    assert check.running is None
    assert check.message == "M1 er målt."


def test_a_voice_strongest_on_another_mic_is_a_wrong_channel() -> None:
    check = MicCheck([M1, M2])
    check.start_talk(M1, 0)
    talk(check, {M1: -30.0, M2: -18.0})  # the person spoke into M2, or the faders are swapped
    assert not check.results[M1].right_channel
    assert check.results[M1].loudest_other == M2
    assert "sterkest på M2" in (check.message or "")
    assert not check.done()


def test_too_little_speech_asks_again() -> None:
    check = MicCheck([M1])
    check.start_talk(M1, 0)
    talk(check, {M1: -70.0})
    assert M1 not in check.results
    assert "hørte ikke nok tale" in (check.message or "")


def test_a_new_take_replaces_the_old_one() -> None:
    check = MicCheck([M1, M2])
    check.start_talk(M1, 0)
    talk(check, {M1: -18.0, M2: -30.0})
    check.start_talk(M1, 10_000)
    talk(check, {M1: -18.0, M2: -40.0}, start=10_000)
    assert check.results[M1].leak_db == {M2: -22.0}


def test_noise_floor_and_baseline() -> None:
    check = MicCheck([M1, M2])
    check.start_noise(0)
    talk(check, {M1: -71.0, M2: -68.0}, ms=NOISE_MS)
    assert check.noise_floor == {M1: -71.0, M2: -68.0}
    check.start_talk(M1, 5_000)
    talk(check, {M1: -18.0, M2: -40.0}, start=5_000)
    at = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
    b = check.baseline(Baseline(), "tekniker1", at)
    assert b.audio.leak_db == {M1: {M2: -22.0}}
    assert b.audio.noise_floor_db == {M1: -71.0, M2: -68.0}
    assert (b.approved_by, b.approved_at) == ("tekniker1", at)


def test_baseline_yaml_round_trip(tmp_path: Path) -> None:
    site = tmp_path / "site"
    shutil.copytree(ROOT / "site" / "example", site)
    b = Baseline(approved_by="tekniker1")
    b = b.model_copy(update={"audio": b.audio.model_copy(update={"leak_db": {M1: {M2: -21.5}}})})
    write_baseline(site / "baseline.yaml", b)
    assert load_site(site).baseline.audio.leak_db == {M1: {M2: -21.5}}
    assert (site / "baseline.yaml").read_text(encoding="utf-8").startswith("# Fasit")


def test_audio_capture_takes_the_new_matrix_at_once() -> None:
    a = Analyzer()
    apply_config(a, {"leak_db": {"M1": {"M2": -12.5}}})
    assert a.leak.gain(M1, M2) == -12.5
    apply_config(a, {"leak_db": {"M9": {}}})  # nonsense is ignored
    assert a.leak.gain(M1, M2) == -12.5


# -- through the API, in the simulator ----------------------------------------------------------


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    r = Rig(tmp_path)
    yield r
    r.store.close()


def test_mic_check_in_the_simulator(rig: Rig) -> None:
    c = rig.client
    st = c.get("/api/setup/mics").json()
    assert st["mics"] == ["M1", "M2", "M3", "M4"]
    c.post("/api/sim/talk", json={"participant": "P1", "on": True})
    assert c.post("/api/setup/mics/M1").json()["running"]["mic"] == "M1"
    rig.run(TALK_MS + 200)
    st = c.get("/api/setup/mics").json()
    assert st["results"]["M1"]["right_channel"] is True
    assert st["results"]["M1"]["worst_leak_db"] < -6
    configs: list[dict[str, object]] = []
    rig.sim.studio.on_audio_config = configs.append
    st = c.post("/api/setup/mics/save").json()
    assert st["saved"]["leak_db"]["M1"]
    assert configs
    assert "M1" in configs[0]["leak_db"]  # type: ignore[operator]
    assert any(a["code"] == "SETUP-5" for a in rig.state()["alerts"])


def test_not_during_recording_and_not_for_the_touch_screen(rig: Rig, tmp_path: Path) -> None:
    c = rig.client
    assert c.post("/api/setup/mics/save").status_code == 409  # nothing measured
    c.post("/api/sim/card", json={"card": TEST_CARD})
    rig.run(100)
    c.post("/api/recording", json={"action": "start"})
    rig.run(4000)
    r = c.post("/api/setup/mics/M1")
    assert r.status_code == 409
    assert "under opptak" in r.json()["detail"]
    assert c.post("/api/setup/mics/M9").status_code == 409
    touch = Rig(tmp_path / "t", dev_admin=False)
    try:
        assert touch.client.get("/api/setup/mics").status_code in (401, 403)
    finally:
        touch.store.close()
