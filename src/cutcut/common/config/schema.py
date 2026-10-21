"""Generate JSON Schema for the config files into ``config/schema/`` (spec 12.1).

Run ``uv run python -m cutcut.common.config.schema`` after changing a config model.
A test fails if the committed files differ from what the models produce.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel

from cutcut.common.config.loader import ShowTypes, default_config_dir
from cutcut.common.config.rules import RulePresets
from cutcut.common.models.multiview import MultiviewMap
from cutcut.common.models.show import ShowConfig
from cutcut.common.models.site import Devices

SCHEMAS: dict[str, type[BaseModel]] = {
    "show.schema.json": ShowConfig,
    "rules.schema.json": RulePresets,
    "show_types.schema.json": ShowTypes,
    "multiview_map.schema.json": MultiviewMap,
    "devices.schema.json": Devices,
}


def render(model: type[BaseModel]) -> str:
    schema = model.model_json_schema()
    return json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write_all(schema_dir: Path) -> list[Path]:
    schema_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, model in SCHEMAS.items():
        path = schema_dir / name
        path.write_text(render(model), encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    for path in write_all(default_config_dir() / "schema"):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
