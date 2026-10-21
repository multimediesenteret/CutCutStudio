"""``cutcut sim``: the engine, the simulator and both screens on this PC (SIM-6, spec 12.1).

Nothing here touches real equipment: ATEM, Pearl, card reader and the NTNU API are fakes, and
the synthetic talkers are driven from the control API (``/api/sim/...``) or the simulator panel.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from cutcut.api.app import create_app
from cutcut.common.clock import SystemClock
from cutcut.sim.live import SIM_PIN, build_live_sim, sim_routes

DEFAULT_PORT = 8080


def default_ui_dir() -> Path:
    """``ui/dist`` in a source checkout (built by ``pnpm build``)."""
    return Path(__file__).resolve().parents[3] / "ui" / "dist"


@dataclass(frozen=True)
class SimOptions:
    host: str = "127.0.0.1"
    port: int = DEFAULT_PORT
    seed: int = 1
    ui_dir: Path | None = None


def build_sim_app(opts: SimOptions) -> FastAPI:
    sim, auth = build_live_sim(SystemClock(), seed=opts.seed)
    return create_app(
        sim.studio,
        auth,
        ui_dir=opts.ui_dir,
        run_loop=True,
        before_tick=sim.before_tick,
        extra_routes=sim_routes(sim),
    )


def banner(opts: SimOptions) -> str:
    base = f"http://{opts.host}:{opts.port}"
    lines = [
        "CutCut Studio – simulator (ingen ekte utstyr)",
        f"  Touch:     {base}/touch/",
        f"  Tekniker:  {base}/tech/",
        f"  API:       {base}/api/docs",
        f"  Testkort:  04A1B2C3, 04D4E5F6 · PIN for tekniker: {SIM_PIN}",
    ]
    if opts.ui_dir is None or not opts.ui_dir.is_dir():
        lines.append("  (Skjermene er ikke bygget: kjør «pnpm install && pnpm build» først.)")
    return "\n".join(lines)


def serve(opts: SimOptions) -> int:
    app = build_sim_app(opts)
    print(banner(opts), flush=True)
    uvicorn.run(app, host=opts.host, port=opts.port, log_level="warning")
    return 0


def smoke(opts: SimOptions, run_s: float = 2.0) -> int:
    """Start the real server, let the engine tick, check health and the screens, stop.

    This is what CI runs for SIM-6: the README command, end to end over HTTP.
    """
    app = build_sim_app(opts)
    config = uvicorn.Config(app, host="127.0.0.1", port=opts.port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{opts.port}"
    try:
        deadline = time.monotonic() + 15
        while not server.started:
            if time.monotonic() > deadline or not thread.is_alive():
                print("FEIL: serveren startet ikke")
                return 1
            time.sleep(0.05)
        time.sleep(run_s)
        with urllib.request.urlopen(f"{base}/api/health", timeout=5) as res:  # noqa: S310
            health = json.load(res)
        runtime = health.get("runtime", {})
        print(f"health: {health['status']} · ticks: {runtime.get('ticks')}")
        if not runtime.get("ticks"):
            print("FEIL: motoren tikker ikke")
            return 1
        if opts.ui_dir is not None and opts.ui_dir.is_dir():
            for screen in ("touch", "tech"):
                with urllib.request.urlopen(f"{base}/{screen}/", timeout=5) as res:  # noqa: S310
                    if b'id="root"' not in res.read():
                        print(f"FEIL: /{screen}/ mangler")
                        return 1
                print(f"/{screen}/: ok")
        return 0
    finally:
        server.should_exit = True
        with contextlib.suppress(RuntimeError):
            thread.join(timeout=10)
