"""``cutcut audio``: the audio-capture process on the bus."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import zmq.asyncio

from cutcut.audio.analyzer import Analyzer
from cutcut.audio.backend import WavBackend
from cutcut.audio.process import run
from cutcut.common.bus.zmq_bus import EVENTS_IN_PORT, Publisher, endpoint
from cutcut.common.clock import SystemClock

log = logging.getLogger(__name__)


def main(wav: Path | None, vad_model: Path | None, site_dir: Path | None = None) -> int:
    if wav is None:
        print("Ekte lydkort (ASIO) kommer i AU-5. Bruk --wav for å spille av en fil.")
        return 2
    backend = WavBackend(wav)
    leak_db = None
    if site_dir is not None:
        from cutcut.common.config import load_site

        leak_db = load_site(site_dir).baseline.audio.leak_db or None
    analyzer = Analyzer(vad_model=vad_model, leak_db=leak_db)

    async def go() -> None:
        ctx = zmq.asyncio.Context.instance()
        pub = Publisher(ctx, "audio-capture", SystemClock(), connect=endpoint(EVENTS_IN_PORT))
        try:
            await run(backend, analyzer, pub.publish)
        finally:
            pub.close()

    matrix = "målt (baseline.yaml)" if leak_db else "standard"
    print(f"audio-capture: {wav.name}, VAD {analyzer.vad_name}, lekkasje {matrix}")
    asyncio.run(go())
    return 0
