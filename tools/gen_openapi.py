"""Write the API description to docs/reference/openapi.json (spec 12.1).

    uv run python tools/gen_openapi.py

The UI types are generated from this file, so the screens and the engine cannot disagree
about a field (spec 12.5). A test fails if the committed file is stale.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "reference" / "openapi.json"


def render() -> str:
    from cutcut.api.app import create_app
    from cutcut.common.clock import FakeClock
    from cutcut.sim.live import build_live_sim

    sim, auth = build_live_sim(FakeClock())
    app = create_app(sim.studio, auth, run_loop=False)
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
