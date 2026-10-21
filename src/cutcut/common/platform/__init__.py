"""Platform adapters (docs/stack.md "Windows-ting bak adaptere", docs/plans/common.md C-7).

Everything Windows-specific sits behind a small interface with a fake implementation, so the
rest of CutCut runs and is tested on Linux. Adapters added later (ASIO audio, capture, WinSW,
kiosk) follow the same pattern in their own modules.

``get_platform()`` returns the real adapters on the studio PC and fakes elsewhere, or always
fakes when ``CUTCUT_FAKE_PLATFORM=1`` (simulator, CI).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from cutcut.common.platform.secrets import FakeSecretStore, KeyringSecretStore, SecretStore
from cutcut.common.platform.system import FakeSystem, PsutilSystem, System, SystemSnapshot


@dataclass(frozen=True)
class Platform:
    name: str
    secrets: SecretStore
    system: System


def is_fake_requested() -> bool:
    return os.environ.get("CUTCUT_FAKE_PLATFORM", "") == "1"


def get_platform(*, fake: bool | None = None) -> Platform:
    use_fake = is_fake_requested() if fake is None else fake
    if use_fake or sys.platform != "win32":
        return Platform(name="fake", secrets=FakeSecretStore(), system=FakeSystem())
    return Platform(name="windows", secrets=KeyringSecretStore(), system=PsutilSystem())


__all__ = [
    "FakeSecretStore",
    "FakeSystem",
    "KeyringSecretStore",
    "Platform",
    "PsutilSystem",
    "SecretStore",
    "System",
    "SystemSnapshot",
    "get_platform",
    "is_fake_requested",
]
