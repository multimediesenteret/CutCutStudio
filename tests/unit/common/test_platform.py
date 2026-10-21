from __future__ import annotations

from pathlib import Path

import pytest

from cutcut.common.platform import (
    FakeSecretStore,
    FakeSystem,
    PsutilSystem,
    get_platform,
)
from cutcut.common.platform.secrets import SecretMissingError


def test_fake_platform_on_linux_and_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    assert get_platform(fake=True).name == "fake"
    monkeypatch.setenv("CUTCUT_FAKE_PLATFORM", "1")
    assert get_platform().name == "fake"


def test_fake_secrets_never_echo_values_in_errors() -> None:
    store = FakeSecretStore()
    assert not store.has("ntnu_api_key")
    with pytest.raises(SecretMissingError, match="ntnu_api_key"):
        store.get("ntnu_api_key")
    store.set("pearl_password", "hemmelig-verdi")
    assert store.get("pearl_password") == "hemmelig-verdi"
    with pytest.raises(SecretMissingError) as exc:
        store.get("canon_password")
    assert "hemmelig-verdi" not in str(exc.value)


def test_unknown_secret_name_is_refused() -> None:
    with pytest.raises(KeyError, match="unknown secret"):
        FakeSecretStore().set("whatever", "x")


def test_fake_system_is_adjustable() -> None:
    sys_ = FakeSystem()
    snap = sys_.snapshot(Path("."))
    assert snap.disk_free_percent == 80.0
    sys_.set_priority("high")
    assert sys_.priority == "high"


def test_psutil_system_gives_real_numbers(tmp_path: Path) -> None:
    snap = PsutilSystem().snapshot(tmp_path)
    assert 0 <= snap.memory_percent <= 100
    assert snap.disk_free_gb > 0
    assert snap.process_rss_mb > 0
    assert snap.uptime_s > 0
