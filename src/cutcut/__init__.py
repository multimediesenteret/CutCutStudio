"""CutCut Studio – live auto-regi for videopodcast.

See AGENTS.md and docs/plans/ for how the code is organised.
"""

import json as _json
from pathlib import Path as _Path


def _version() -> str:
    """The package version from ``BUILD.json`` in the Windows package (SO-3), else the source
    tree's own."""
    try:
        data = _json.loads((_Path(__file__).resolve().parents[2] / "BUILD.json").read_text("utf-8"))
        return str(data["version"])
    except (OSError, ValueError, KeyError, TypeError):
        return "0.1.0.dev0"


__version__ = _version()
