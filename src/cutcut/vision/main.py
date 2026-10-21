"""``cutcut vision``: the video layer as its own process on the bus (started by supervisor)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import zmq.asyncio

from cutcut.common.bus.zmq_bus import EVENTS_IN_PORT, Publisher, endpoint, use_selector_event_loop
from cutcut.common.clock import SystemClock
from cutcut.common.config import load_site
from cutcut.vision.capture import OpenCvSource, Source, SyntheticSource
from cutcut.vision.process import run

log = logging.getLogger(__name__)


def main(site_dir: Path, device: int | None, file: Path | None, synthetic: bool) -> int:
    site = load_site(site_dir)
    if site.multiview is None:
        print("Studio-oppsettet mangler equipment/multiview_map.yaml (rutekartet).")
        return 2
    source: Source
    if synthetic:
        source = SyntheticSource(site.multiview)
    elif file is not None:
        source = OpenCvSource(str(file))
    else:
        source = OpenCvSource(device if device is not None else 0)

    async def go() -> None:
        ctx = zmq.asyncio.Context.instance()
        pub = Publisher(ctx, "vision", SystemClock(), connect=endpoint(EVENTS_IN_PORT))
        try:
            await run(source, site.multiview, pub.publish)  # type: ignore[arg-type]
        finally:
            source.close()
            pub.close()

    print(f"vision: {source.name} · {len(site.multiview.tiles)} ruter")
    use_selector_event_loop()
    asyncio.run(go())
    return 0
