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


def main(wav: Path | None, vad_model: Path | None) -> int:
    if wav is None:
        print("Ekte lydkort (ASIO) kommer i AU-5. Bruk --wav for å spille av en fil.")
        return 2
    backend = WavBackend(wav)
    analyzer = Analyzer(vad_model=vad_model)

    async def go() -> None:
        ctx = zmq.asyncio.Context.instance()
        pub = Publisher(ctx, "audio-capture", SystemClock(), connect=endpoint(EVENTS_IN_PORT))
        try:
            await run(backend, analyzer, pub.publish)
        finally:
            pub.close()

    print(f"audio-capture: {wav.name}, VAD {analyzer.vad_name}")
    asyncio.run(go())
    return 0
