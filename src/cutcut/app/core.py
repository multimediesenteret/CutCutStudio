"""``cutcut core``: the studio process with real equipment (M2).

Wires the same :class:`~cutcut.app.studio.Studio` that the simulator runs to the real devices:

* Companion (cuts via preview + TAKE, ``regi_*`` variables) with atem-bridge as the reserve
  path (``S5``) – :mod:`cutcut.devices.companion`, :mod:`cutcut.devices.atem`;
* atem-bridge over the bus for what the ATEM shows and its multiview;
* Pearl as the recorder – :mod:`cutcut.devices.pearl`;
* audio-capture over the bus (``audio.frame``) – :mod:`cutcut.audio`.

The bus is bound here (core is the hub): events in on 5560, commands out on 5561. Every
device client works in its own thread or over the bus, so the engine never waits for one
(ADR-0005). If a device is missing, the studio still starts and shows it under Helse.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import zmq.asyncio
from fastapi import FastAPI

from cutcut.api.app import create_app
from cutcut.api.auth import Auth
from cutcut.app import devices as device_settings
from cutcut.app.maintenance import Maintenance
from cutcut.app.studio import Studio, StudioDeps
from cutcut.common.bus.zmq_bus import (
    EVENTS_IN_PORT,
    EVENTS_OUT_PORT,
    Publisher,
    Subscriber,
    use_selector_event_loop,
)
from cutcut.common.clock import SystemClock
from cutcut.common.config import load_rule_presets, load_show_types, load_site
from cutcut.common.models.site import Devices, SmtpConfig, Staff
from cutcut.common.platform.mail import SmtpMailer
from cutcut.common.platform.secrets import SecretMissingError, SecretStore
from cutcut.common.platform.system import PsutilSystem
from cutcut.common.store import Store
from cutcut.devices.atem.bridge import AtemBridgeClient, site_input_map
from cutcut.devices.cameras.guarded import on_air
from cutcut.devices.cameras.service import CameraService
from cutcut.devices.companion.client import CompanionHttp
from cutcut.devices.companion.executor import CompanionExecutor
from cutcut.devices.pearl.client import PearlHttp
from cutcut.devices.pearl.recorder import PearlRecorder

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CoreOptions:
    site_dir: Path
    data_dir: Path
    secrets: SecretStore
    host: str = "127.0.0.1"
    port: int = 8080
    ui_dir: Path | None = None
    bus_in_port: int = EVENTS_IN_PORT
    bus_out_port: int = EVENTS_OUT_PORT


@dataclass
class Core:
    """Everything ``cutcut core`` runs, kept together so tests can look inside."""

    app: FastAPI
    studio: Studio
    bridge: AtemBridgeClient
    companion: CompanionExecutor
    pearl: PearlRecorder
    store: Store
    cameras: CameraService | None = None
    _closers: list[Any] = field(default_factory=list)

    def close(self) -> None:
        for c in self._closers:
            with contextlib.suppress(Exception):
                c()


def _pearl_api(dev: Devices, secrets: SecretStore) -> PearlHttp:
    try:
        password = secrets.get("pearl_password")
    except SecretMissingError:
        log.error("pearl_password mangler i Credential Manager; Pearl vil avvise innlogging")
        password = ""
    p = dev.pearl
    port = f":{p.port}" if p.port else ""
    return PearlHttp(f"{p.scheme}://{p.ip}{port}", p.username, password, verify_tls=p.verify_tls)


def _mailer(secrets: SecretStore) -> Callable[[SmtpConfig, list[str], str, str], None]:
    """Email alerts (HS-3). The relay's password, if it needs one, is ``smtp_password``."""

    def send(cfg: SmtpConfig, to: list[str], subject: str, body: str) -> None:
        password = ""
        if cfg.username:
            try:
                password = secrets.get("smtp_password")
            except SecretMissingError:
                log.error("smtp_password mangler i Credential Manager")
        SmtpMailer(cfg, password).send(to, subject, body)

    return send


def build_core(opts: CoreOptions) -> Core:
    site = load_site(opts.site_dir)
    opts.data_dir.mkdir(parents=True, exist_ok=True)
    store = Store(opts.data_dir / "cutcut.db")
    clock = SystemClock()

    # Addresses changed on screen win over devices.yaml from the very first connection.
    saved = store.get_kv(device_settings.DEVICES_KEY)
    try:
        dev = device_settings.apply(site.devices, dict(saved or {}))
    except device_settings.DeviceSettingsError as exc:
        log.warning("Lagrede utstyrsadresser ble ikke brukt: %s", exc)
        dev = site.devices

    ctx = zmq.asyncio.Context()
    pub = Publisher(ctx, "core", clock, bind=f"tcp://127.0.0.1:{opts.bus_out_port}")
    sub = Subscriber(ctx, bind=f"tcp://127.0.0.1:{opts.bus_in_port}")
    loop_ref: dict[str, asyncio.AbstractEventLoop] = {}

    def send(topic: str, payload: dict[str, Any]) -> None:
        """Publish from any thread (the Companion executor's fallback runs off-loop)."""
        loop = loop_ref.get("loop")
        if loop is None:
            log.warning("bussen er ikke klar; %s ble ikke sendt", topic)
            return
        asyncio.run_coroutine_threadsafe(pub.publish(topic, payload), loop)

    bridge = AtemBridgeClient(send, site_input_map(list(site.shows.values())))
    companion_api = CompanionHttp(str(dev.companion.url))
    companion = CompanionExecutor(
        companion_api,
        site.companion_map,
        engine_page=dev.companion.engine_page,
        operator_page=dev.companion.operator_page,
        fallback=bridge,
    )
    pearl = PearlRecorder(_pearl_api(dev, opts.secrets), recorder_id=dev.pearl.recorder_id)
    # PTZ cameras: what is on air comes from the ATEM read-back, never from the engine (I2)
    cameras = CameraService.from_devices(
        dev, lambda: on_air(bridge.readback(), list(site.devices.cameras))
    )

    studio = Studio(
        StudioDeps(
            site=site,
            show_types=load_show_types(),
            presets=load_rule_presets(),
            clock=clock,
            executor=companion,
            recorder=pearl,
            store=store,
            log_dir=opts.data_dir / "logs",
            atem=bridge,
            system=PsutilSystem(),
            data_dir=opts.data_dir,
            cameras=cameras,
            send_mail=_mailer(opts.secrets),
        )
    )
    cameras.on_moving = studio.runtime.feed_cameras_moving  # S1, from the position read-back
    upkeep = Maintenance(
        store,
        opts.data_dir / "backup",
        lambda: datetime.now().astimezone(),
        lambda: studio.sessions.session is not None,
    )

    def on_devices(new: Devices) -> None:
        companion.api = CompanionHttp(str(new.companion.url))
        pearl.api = _pearl_api(new, opts.secrets)
        cameras.reconfigure(new)
        log.info("Nye utstyrsadresser tatt i bruk (ATEM: ved neste omstart av atem-bridge)")

    studio.on_devices = on_devices
    studio.on_audio_config = lambda cfg: send("audio.config", cfg)  # setup step 5 → audio-capture
    studio.on_vision_want = lambda: send("vision.want", {})  # thumbnails while someone looks
    studio.on_vision_map = lambda m: send("vision.map", m.model_dump(mode="json"))

    async def map_pusher() -> None:
        """The rutekart saved in the app, again every 10 s: a restarted video layer reads the
        file first and gets this within seconds (VI-5)."""
        while True:
            if studio.multiview_in_app and studio.deps.site.multiview is not None:
                send("vision.map", studio.deps.site.multiview.model_dump(mode="json"))
            await asyncio.sleep(10)

    def before_tick() -> None:
        studio.runtime.feed_atem(bridge.readback())

    async def bus_reader() -> None:
        loop_ref["loop"] = asyncio.get_running_loop()
        while True:
            msg = await sub.recv()
            if msg is None:
                continue
            if msg.topic.startswith("atem."):
                bridge.on_message(msg.topic, msg.payload)
            elif msg.topic == "supervisor.status":
                studio.on_supervisor(msg.payload)
            else:
                studio.runtime.feed_bus(msg.topic, msg.payload)

    auth = Auth(studio.staff, opts.secrets)  # the list from the app, else staff.yaml

    def on_staff(staff: Staff) -> None:
        auth.staff = staff

    studio.on_staff = on_staff
    app = create_app(
        studio,
        auth,
        ui_dir=opts.ui_dir,
        before_tick=before_tick,
        background=[bus_reader, cameras.run, upkeep.run, map_pusher],
    )
    core = Core(app, studio, bridge, companion, pearl, store, cameras)
    core._closers += [
        companion.close,
        pearl.close,
        cameras.close,
        pub.close,
        sub.close,
        store.close,
        ctx.term,
    ]
    return core


def default_data_dir() -> Path:
    """``C:\\ProgramData\\CutCut\\data`` on Windows (spec 9.2), ``./data`` elsewhere."""
    import os
    import sys

    if sys.platform == "win32":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "CutCut" / "data"
    return Path("data")


def serve(opts: CoreOptions) -> int:
    import uvicorn

    core = build_core(opts)
    print(
        f"CutCut Studio core · {core.studio.devices.studio} · http://{opts.host}:{opts.port}/tech/"
    )
    try:
        # The bus needs a selector loop on Windows. uvicorn's own «asyncio» setting picks the
        # proactor loop there, so «none»: uvicorn then uses the policy set here.
        use_selector_event_loop()
        uvicorn.run(core.app, host=opts.host, port=opts.port, log_level="warning", loop="none")
    finally:
        core.close()
    return 0
