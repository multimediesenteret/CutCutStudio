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
        "--smoke", action="store_true", help="start, sjekk helse og skjermer, avslutt (CI)"
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
        )
        return smoke(opts) if args.smoke else serve(opts)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
