"""Load and validate YAML configuration (spec 4, 12.3; ADR-0006).

* Files are read with a safe YAML loader and validated with Pydantic.
* ``schema_version`` is checked: older files are migrated in memory, newer files are refused
  (the app must never run on a config it does not understand, spec 12.3).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from cutcut.common.config.rules import RuleParams, RulePresets
from cutcut.common.models.show import SHOW_SCHEMA_VERSION, RulesPreset, ShowConfig


class ConfigError(Exception):
    """Configuration could not be loaded. ``str()`` is a readable message for the log and UI."""


class ShowType(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    rules_preset: RulesPreset
    audio_only: bool = False
    iso_record: bool = False


class ShowTypes(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    default: str
    types: dict[str, ShowType] = Field(min_length=1)

    def get(self, type_id: str | None) -> tuple[str, ShowType]:
        key = type_id or self.default
        if key not in self.types:
            raise ConfigError(f"ukjent show-type {key!r}")
        return key, self.types[key]


Migration = Callable[[dict[str, Any]], dict[str, Any]]

# from_version -> function that returns the data at from_version + 1.
SHOW_MIGRATIONS: dict[int, Migration] = {}


def default_config_dir() -> Path:
    """``CUTCUT_CONFIG_DIR`` if set, otherwise ``config/`` next to the source tree."""
    env = os.environ.get("CUTCUT_CONFIG_DIR")
    if env:
        return Path(env)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "config" / "defaults"
        if candidate.is_dir():
            return parent / "config"
    raise ConfigError("fant ikke config/defaults; sett CUTCUT_CONFIG_DIR")


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"filen finnes ikke: {path}") from exc
    except YAMLError as exc:
        raise ConfigError(f"ugyldig YAML i {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} må inneholde et YAML-objekt")
    return data


def migrate(
    data: dict[str, Any], current: int, migrations: dict[int, Migration], what: str
) -> dict[str, Any]:
    version = data.get("schema_version", 1)
    if not isinstance(version, int) or version < 1:
        raise ConfigError(f"{what}: ugyldig schema_version {version!r}")
    if version > current:
        raise ConfigError(
            f"{what}: schema_version {version} er nyere enn denne versjonen av CutCut "
            f"forstår ({current}). Oppdater CutCut eller bruk en eldre fil."
        )
    while version < current:
        step = migrations.get(version)
        if step is None:
            raise ConfigError(f"{what}: mangler migrering fra schema_version {version}")
        data = step(dict(data))
        version += 1
        data["schema_version"] = version
    return data


def _validate[M: BaseModel](model: type[M], data: dict[str, Any], what: str) -> M:
    try:
        return model.model_validate(data)
    except ValueError as exc:  # pydantic.ValidationError is a ValueError
        raise ConfigError(f"{what} er ugyldig:\n{exc}") from exc


def load_show(path: Path) -> ShowConfig:
    data = migrate(read_yaml(path), SHOW_SCHEMA_VERSION, SHOW_MIGRATIONS, str(path))
    return _validate(ShowConfig, data, str(path))


def load_rule_presets(config_dir: Path | None = None) -> RulePresets:
    path = (config_dir or default_config_dir()) / "defaults" / "rules.yaml"
    return _validate(RulePresets, read_yaml(path), str(path))


def load_show_types(config_dir: Path | None = None) -> ShowTypes:
    path = (config_dir or default_config_dir()) / "defaults" / "show_types.yaml"
    return _validate(ShowTypes, read_yaml(path), str(path))


def effective_rules(show: ShowConfig, presets: RulePresets) -> RuleParams:
    """Preset values for the show, with the show's ``rules_override`` applied."""
    try:
        return presets.get(show.rules_preset).with_overrides(show.rules_override)
    except ValueError as exc:
        raise ConfigError(f"show {show.id}: {exc}") from exc
