"""Command line entry point: ``uv run cutcut``.

Sub-commands are added as the modules are built (``cutcut sim`` in SIM-6).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from cutcut import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cutcut", description="CutCut Studio")
    parser.add_argument("--version", action="version", version=f"cutcut {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
