"""``cutcut audio``: the audio-capture process on the bus."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import zmq.asyncio

from cutcut.audio.analyzer import Analyzer
from cutcut.audio.backend import Backend, WavBackend
from cutcut.audio.device import DeviceBackend
from cutcut.audio.process import run
from cutcut.common.bus.zmq_bus import (
    EVENTS_IN_PORT,
    EVENTS_OUT_PORT,
    Publisher,
    Subscriber,
    endpoint,
    use_selector_event_loop,
)
from cutcut.common.clock import SystemClock
from cutcut.common.ids import MicId
from cutcut.common.models.site import AudioDevice

log = logging.getLogger(__name__)


async def listen_config(sub: Subscriber, analyzer: Analyzer) -> None:
    """``audio.config`` from core: the leakage measured in setup step 5, used at once."""
    while True:
        msg = await sub.recv()
        if msg is None or msg.topic != "audio.config":
            continue
        apply_config(analyzer, msg.payload)


def apply_config(analyzer: Analyzer, payload: dict[str, Any]) -> None:
    raw = payload.get("leak_db")
    if not isinstance(raw, dict):
        return
    try:
        leak = {MicId(s): {MicId(d): float(v) for d, v in row.items()} for s, row in raw.items()}
    except (ValueError, TypeError, AttributeError) as exc:
        log.warning("ugyldig audio.config: %s", exc)
        return
    analyzer.leak.leak_db = leak
    log.info("Ny lekkasjematrise fra setup (%d mic-er)", len(leak))


def main(wav: Path | None, vad_model: Path | None, site_dir: Path | None = None) -> int:
    """``--wav`` plays a file (fake); without it the RØDECaster is opened (ASIO, then WASAPI)."""
    leak_db = None
    audio_cfg = AudioDevice()
    if site_dir is not None:
        from cutcut.common.config import load_site

        site = load_site(site_dir)
        leak_db = site.baseline.audio.leak_db or None
        audio_cfg = site.devices.audio
    backend: Backend
    if wav is not None:
        backend = WavBackend(wav)
        source = wav.name
    else:
        backend = DeviceBackend(audio_cfg)
        source = f"«{audio_cfg.device}» via {audio_cfg.backend}, {audio_cfg.channels} kanaler"
    analyzer = Analyzer(vad_model=vad_model, leak_db=leak_db)

    async def go() -> None:
        ctx = zmq.asyncio.Context.instance()
        pub = Publisher(ctx, "audio-capture", SystemClock(), connect=endpoint(EVENTS_IN_PORT))
        sub = Subscriber(ctx, connect=endpoint(EVENTS_OUT_PORT), topics=["audio.config"])
        config = asyncio.create_task(listen_config(sub, analyzer))
        try:
            await run(backend, analyzer, pub.publish)
        finally:
            config.cancel()
            backend.close()
            sub.close()
            pub.close()

    matrix = "målt (baseline.yaml)" if leak_db else "standard"
    print(f"audio-capture: {source}, VAD {analyzer.vad_name}, lekkasje {matrix}")
    use_selector_event_loop()  # the bus needs it on Windows
    asyncio.run(go())
    return 0
