"""Command line entry point: ``uv run cutcut``.

Sub-commands are added as the modules are built.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from cutcut import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cutcut", description="CutCut Studio")
    parser.add_argument("--version", action="version", version=f"cutcut {__version__}")
    sub = parser.add_subparsers(dest="command")

    sim = sub.add_parser(
        "sim",
        help="kjør motor, simulator og begge skjermer lokalt (ingen ekte utstyr)",
        description="Starter studioet på simulert utstyr. Åpne /touch/ og /tech/ i nettleseren.",
    )
    sim.add_argument("--host", default="127.0.0.1", help="adresse (standard 127.0.0.1)")
    sim.add_argument("--port", type=int, default=8080, help="port (standard 8080)")
    sim.add_argument("--seed", type=int, default=1, help="frø for syntetisk samtale")
    sim.add_argument("--ui-dir", type=Path, default=None, help="bygde skjermer (ui/dist)")
    sim.add_argument(
        "--site",
        type=Path,
        default=None,
        help="studio-oppsett, f.eks. site/ntnu-studio (standard: det fiktive site/example)",
    )
    sim.add_argument(
        "--smoke", action="store_true", help="start, sjekk helse og skjermer, avslutt (CI)"
    )

    core = sub.add_parser(
        "core",
        help="kjør studioet med ekte utstyr (Companion, ATEM via atem-bridge, Pearl, lyd)",
        description="Startes av supervisor i studio. Skjermene på /touch/ og /tech/.",
    )
    core.add_argument(
        "--site", type=Path, required=True, help="studio-oppsett, f.eks. site/ntnu-studio"
    )
    core.add_argument("--data", type=Path, default=None, help="database og logger")
    core.add_argument("--host", default="127.0.0.1")
    core.add_argument("--port", type=int, default=8080)
    core.add_argument("--ui-dir", type=Path, default=None, help="bygde skjermer (ui/dist)")

    audio = sub.add_parser(
        "audio",
        help="kjør audio-capture: mikrofoner til målinger på bussen (ADR-0014)",
        description="Leser multitrack fra RØDECaster (eller en WAV-fil) og sender audio.frame.",
    )
    audio.add_argument("--wav", type=Path, help="spill av en 48 kHz multitrack-WAV (fake)")
    audio.add_argument("--vad-model", type=Path, default=None, help="Silero VAD (.onnx)")

    trace = sub.add_parser(
        "trace",
        help="skriv simulerte forløp som JSON for web-simulatoren (Vercel)",
        description="Kjører motoren på falsk klokke og lagrer alt skjermene ville fått.",
    )
    trace.add_argument("--out", type=Path, default=None, help="mappe (standard: simulatorens)")
    trace.add_argument(
        "--check", action="store_true", help="skriv ingenting; feil hvis forløpene er utdaterte"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "sim":
        from cutcut.sim.serve import SimOptions, default_ui_dir, serve, smoke

        opts = SimOptions(
            host=args.host,
            port=args.port,
            seed=args.seed,
            ui_dir=args.ui_dir or default_ui_dir(),
            site_dir=args.site,
        )
        return smoke(opts) if args.smoke else serve(opts)
    if args.command == "core":
        from cutcut.app.core import CoreOptions, default_data_dir
        from cutcut.app.core import serve as serve_core
        from cutcut.common.platform import get_platform
        from cutcut.sim.serve import default_ui_dir as ui_default

        return serve_core(
            CoreOptions(
                site_dir=args.site,
                data_dir=args.data or default_data_dir(),
                secrets=get_platform().secrets,
                host=args.host,
                port=args.port,
                ui_dir=args.ui_dir or ui_default(),
            )
        )
    if args.command == "audio":
        from cutcut.audio.main import main as audio_main

        return audio_main(args.wav, args.vad_model)
    if args.command == "trace":
        from cutcut.sim.trace import default_trace_dir, write_all

        out = args.out or default_trace_dir()
        changed = write_all(out, check=args.check)
        if args.check and changed:
            print("Utdaterte forløp (kjør «uv run cutcut trace»): " + ", ".join(changed))
            return 1
        print(
            "Forløpene er oppdatert."
            if args.check
            else f"Skrev: {', '.join(changed) or 'ingen endringer'}"
        )
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
