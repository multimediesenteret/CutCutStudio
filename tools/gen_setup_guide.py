"""Write the printed setup guide to docs/setup/README.md (spec 8.4, 12.1; HS-5).

    uv run python tools/gen_setup_guide.py

The guide is made from the same step files as the setup helper on the technician screen
(``config/defaults/setup/*.yaml``), so the two cannot differ. A test fails if the committed
guide is stale.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "setup" / "README.md"


def render() -> str:
    from cutcut.setup.steps import guide_markdown, load_steps

    return guide_markdown(load_steps(ROOT / "config" / "defaults" / "setup"))


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
