"""``cutcut supervisor``: starts core, atem-bridge and audio-capture and keeps them running.

Run as a Windows service (WinSW, SO-2) in the studio. The ATEM address is read again before
each start of atem-bridge, so an address changed on the setup screen is used after the next
restart of the bridge («Start atem-bridge på nytt» or a crash).
"""

from __future__ import annotations

import contextlib
import json
import logging
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

from cutcut.app import devices as device_settings
from cutcut.common.config import load_site
from cutcut.supervisor.report import StatusReporter
from cutcut.supervisor.supervisor import ProcessSpec, Supervisor

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class SupervisorOptions:
    site_dir: Path
    data_dir: Path
    port: int = 8080
    ui_dir: Path | None = None
    bridge_dir: Path = REPO / "bridges" / "atem"
    audio_wav: Path | None = None  # until AU-5 brings the real sound card


def effective_atem_ip(site_dir: Path, data_dir: Path) -> str:
    """devices.yaml with the addresses saved on screen applied (read-only, never blocks core)."""
    site = load_site(site_dir)
    saved: dict[str, str] = {}
    db = data_dir / "cutcut.db"
    if db.exists():
        with contextlib.suppress(sqlite3.Error, ValueError):
            conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=2)
            try:
                row = conn.execute(
                    "SELECT value FROM kv WHERE key=?", (device_settings.DEVICES_KEY,)
                ).fetchone()
            finally:
                conn.close()
            if row:
                saved = {str(k): str(v) for k, v in json.loads(row[0]).items() if v}
    try:
        dev = device_settings.apply(site.devices, saved)
    except device_settings.DeviceSettingsError as exc:
        log.warning("Lagrede adresser ble ikke brukt: %s", exc)
        dev = site.devices
    return str(dev.atem.ip)


def core_health(port: int) -> bool:
    try:
        return (
            httpx.get(
                f"http://127.0.0.1:{port}/api/health", timeout=2.0, trust_env=False
            ).status_code
            == 200
        )
    except httpx.HTTPError:
        return False


def specs(opts: SupervisorOptions) -> list[ProcessSpec]:
    py = [sys.executable, "-m", "cutcut"]
    core_args = [*py, "core", "--site", str(opts.site_dir), "--data", str(opts.data_dir)]
    core_args += ["--port", str(opts.port)]
    if opts.ui_dir is not None:
        core_args += ["--ui-dir", str(opts.ui_dir)]
    node = shutil.which("node") or "node"
    out = [
        ProcessSpec("core", core_args, health=lambda: core_health(opts.port)),
        ProcessSpec(
            "atem-bridge",
            lambda: [
                node,
                "--experimental-strip-types",
                "src/main.ts",
                "--ip",
                effective_atem_ip(opts.site_dir, opts.data_dir),
            ],
            cwd=opts.bridge_dir,
        ),
    ]
    if opts.audio_wav is not None:
        out.append(
            ProcessSpec(
                "audio-capture",
                [*py, "audio", "--wav", str(opts.audio_wav), "--site", str(opts.site_dir)],
            )
        )
    return out


def run(opts: SupervisorOptions) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    reporter = StatusReporter()

    def flap(name: str, count: int) -> None:
        log.error("H-PROC-1: %s er startet på nytt %d ganger på 10 minutter", name, count)

    sup = Supervisor(specs(opts), on_flap=flap)
    print(f"CutCut supervisor · {', '.join(sup.states)}")
    try:
        sup.run(report=reporter)
    except KeyboardInterrupt:
        pass
    finally:
        reporter.close()
    return 0
