from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path

import pytest

from cutcut.common.clock import FakeClock, SystemClock
from cutcut.common.logging import (
    LOG_RETENTION_DAYS,
    correlation,
    current_correlation_id,
    new_correlation_id,
    setup_logging,
)
from cutcut.common.privacy import REDACTED, redact, redact_text

# The fictional test card (never a real card). Same number in the three formats a reader
# can be configured for: hex, reversed hex and decimal.
TEST_CARD_HEX = "04A1B2C3"
TEST_CARD_HEX_REVERSED = "C3B2A104"
TEST_CARD_DEC = "0077706307"


def test_fake_clock_is_deterministic_and_monotonic() -> None:
    clock = FakeClock()
    start_wall = clock.now()
    clock.advance(250)
    assert clock.mono_ms() == 250
    assert clock.now() - start_wall == timedelta(milliseconds=250)
    with pytest.raises(ValueError, match="backwards"):
        clock.advance(-1)


def test_wall_clock_jump_does_not_move_monotonic_time() -> None:
    clock = FakeClock(mono_ms=1000)
    clock.jump_wall(timedelta(hours=-1))  # NTP correction
    assert clock.mono_ms() == 1000


def test_system_clock_moves_forward() -> None:
    clock = SystemClock()
    a = clock.mono_ms()
    b = clock.mono_ms()
    assert b >= a >= 0
    assert clock.now().tzinfo is not None


@pytest.mark.parametrize(
    "text",
    [
        f"kort {TEST_CARD_HEX} lest",
        f"kort {TEST_CARD_HEX_REVERSED}",
        "uid=04:a1:b2:c3",
        f"desimal {TEST_CARD_DEC}",
        "7 byte 04A1B2C3D4E5F6",
    ],
)
def test_redact_removes_card_numbers(text: str) -> None:
    out = redact_text(text)
    assert REDACTED in out
    for secret in (TEST_CARD_HEX, TEST_CARD_HEX_REVERSED, TEST_CARD_DEC, "04A1B2C3D4E5F6"):
        assert secret.lower() not in out.lower()


@pytest.mark.parametrize("text", ["T2 800 ms", "CU:P2", "N3C", "2026-10-21", "d-120301-17", "C1"])
def test_redact_keeps_normal_text(text: str) -> None:
    assert redact_text(text) == text


def test_redact_sensitive_keys_and_nesting() -> None:
    data = {"user": "kanordm", "card_uid": "anything", "nested": [{"msg": TEST_CARD_HEX}]}
    out = redact(data)
    assert out["user"] == "kanordm"
    assert out["card_uid"] == REDACTED
    assert out["nested"][0]["msg"] == REDACTED


def test_correlation_ids_are_not_hex_like() -> None:
    cid = new_correlation_id()
    assert redact_text(cid) == cid
    with correlation() as outer:
        assert current_correlation_id() == outer
        with correlation("x-1") as inner:
            assert current_correlation_id() == inner == "x-1"
        assert current_correlation_id() == outer
    assert current_correlation_id() is None


def test_json_log_line_has_required_fields_and_is_redacted(tmp_path: Path) -> None:
    log = setup_logging("core", log_dir=tmp_path, console=False)
    with correlation("d-1"):
        log.info("kort %s skannet", TEST_CARD_HEX, extra={"rule": "T2", "run_ms": 520})
    for handler in logging.getLogger().handlers:
        handler.flush()
    lines = (tmp_path / "core.jsonl").read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[-1])
    assert record["process"] == "core"
    assert record["module"] == "cutcut"
    assert record["rule"] == "T2"
    assert record["run_ms"] == 520
    assert record["correlation_id"] == "d-1"
    assert TEST_CARD_HEX not in lines[-1]
    assert REDACTED in record["msg"]


def test_rotation_keeps_thirty_days(tmp_path: Path) -> None:
    setup_logging("core", log_dir=tmp_path, console=False)
    handlers = [h for h in logging.getLogger().handlers if getattr(h, "_cutcut", False)]
    rotating = [h for h in handlers if isinstance(h, logging.handlers.TimedRotatingFileHandler)]
    assert rotating
    assert rotating[0].backupCount == LOG_RETENTION_DAYS == 30
    assert rotating[0].when == "MIDNIGHT"
