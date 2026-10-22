"""PC health numbers for the ``H-PC-*`` checks (spec 8.5) and process priority (ADR-0003)."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

Priority = Literal["high", "normal", "low"]


@dataclass(frozen=True)
class SystemSnapshot:
    cpu_percent: float
    memory_percent: float
    disk_free_gb: float
    disk_free_percent: float
    uptime_s: float
    process_rss_mb: float


@dataclass(frozen=True)
class NetInterface:
    """A network card as Windows names it, whether it is up, and its IPv4 addresses."""

    name: str
    up: bool
    ipv4: tuple[str, ...]


class System(Protocol):
    def snapshot(self, data_dir: Path) -> SystemSnapshot: ...
    def set_priority(self, priority: Priority) -> None: ...
    def interfaces(self) -> list[NetInterface]: ...


class PsutilSystem:
    """Real numbers on any OS via psutil (BSD licence)."""

    def snapshot(self, data_dir: Path) -> SystemSnapshot:
        import psutil

        disk = psutil.disk_usage(str(data_dir))
        return SystemSnapshot(
            cpu_percent=psutil.cpu_percent(interval=None),
            memory_percent=psutil.virtual_memory().percent,
            disk_free_gb=disk.free / 1e9,
            disk_free_percent=100.0 - disk.percent,
            uptime_s=time.time() - psutil.boot_time(),
            process_rss_mb=psutil.Process(os.getpid()).memory_info().rss / 1e6,
        )

    def set_priority(self, priority: Priority) -> None:
        import psutil

        proc = psutil.Process(os.getpid())
        if sys.platform == "win32":
            classes = {
                "high": psutil.HIGH_PRIORITY_CLASS,
                "normal": psutil.NORMAL_PRIORITY_CLASS,
                "low": psutil.BELOW_NORMAL_PRIORITY_CLASS,
            }
            proc.nice(classes[priority])
        elif priority == "low":  # raising priority needs root on Linux; only lower it
            proc.nice(10)

    def interfaces(self) -> list[NetInterface]:
        import socket

        import psutil

        stats = psutil.net_if_stats()
        out = []
        for name, addrs in psutil.net_if_addrs().items():
            ipv4 = tuple(a.address for a in addrs if a.family == socket.AF_INET)
            st = stats.get(name)
            out.append(NetInterface(name, bool(st and st.isup), ipv4))
        return out


class FakeSystem:
    """Fixed numbers, adjustable from tests and the simulator (to fake a full disk etc.)."""

    def __init__(self, snapshot: SystemSnapshot | None = None) -> None:
        self.value = snapshot or SystemSnapshot(
            cpu_percent=12.0,
            memory_percent=35.0,
            disk_free_gb=400.0,
            disk_free_percent=80.0,
            uptime_s=3600.0,
            process_rss_mb=120.0,
        )
        self.priority: Priority = "normal"
        # D-064: one card on the studio switch, one on the campus network
        self.nics: list[NetInterface] = [
            NetInterface("Studio", True, ("10.10.10.2",)),
            NetInterface("Campus", True, ("192.168.50.20",)),
            NetInterface("Loopback", True, ("127.0.0.1",)),
        ]

    def snapshot(self, data_dir: Path) -> SystemSnapshot:
        return self.value

    def set_priority(self, priority: Priority) -> None:
        self.priority = priority

    def interfaces(self) -> list[NetInterface]:
        return list(self.nics)
