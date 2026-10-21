"""CI gate (spec 12.1): every implemented rule has tests and code, generated docs are current."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_traceability_is_complete_and_docs_are_current() -> None:
    result = subprocess.run(  # noqa: S603 - our own script
        [sys.executable, str(ROOT / "tools" / "traceability.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
