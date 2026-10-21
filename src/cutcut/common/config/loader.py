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
from cutcut.common.models.baseline import Baseline
from cutcut.common.models.multiview import MultiviewMap
from cutcut.common.models.show import SHOW_SCHEMA_VERSION, RulesPreset, ShowConfig
from cutcut.common.models.site import CompanionMap, Devices, Staff


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


class Site(BaseModel):
    """Everything in ``site/<studio>/``, loaded and cross-checked."""

    model_config = ConfigDict(frozen=True)

    root: Path
    devices: Devices
    staff: Staff
    companion_map: CompanionMap
    shows: dict[str, ShowConfig]
    multiview: MultiviewMap | None = None  # equipment/multiview_map.yaml (spec 6.1)
    baseline: Baseline = Baseline()  # baseline.yaml from the setup wizard; empty before setup


def load_site(root: Path) -> Site:
    """Load a studio folder. Fails with a readable message if anything does not fit together."""
    devices = _validate(Devices, read_yaml(root / "devices.yaml"), str(root / "devices.yaml"))
    staff = _validate(Staff, read_yaml(root / "staff.yaml"), str(root / "staff.yaml"))
    cmap_path = root / "equipment" / "companion_map.yaml"
    companion_map = _validate(CompanionMap, read_yaml(cmap_path), str(cmap_path))
    shows: dict[str, ShowConfig] = {}
    for path in sorted((root / "shows").glob("*.yaml")):
        show = load_show(path)
        if show.id in shows:
            raise ConfigError(f"{path}: show-id {show.id!r} finnes allerede")
        for cam_id, cam in show.cameras.items():
            device = devices.cameras.get(cam_id)
            if device is None:
                raise ConfigError(f"{path}: kamera {cam_id} finnes ikke i devices.yaml")
            if cam.ip is not None and cam.ip != device.ip:
                raise ConfigError(
                    f"{path}: {cam_id} har IP {cam.ip}, devices.yaml sier {device.ip}"
                )
        shows[show.id] = show
    if not shows:
        raise ConfigError(f"{root / 'shows'}: ingen show-oppsett")
    mv_path = root / "equipment" / "multiview_map.yaml"
    multiview = (
        _validate(MultiviewMap, read_yaml(mv_path), str(mv_path)) if mv_path.exists() else None
    )
    bl_path = root / "baseline.yaml"
    baseline = (
        _validate(Baseline, read_yaml(bl_path), str(bl_path)) if bl_path.exists() else Baseline()
    )
    return Site(
        root=root,
        baseline=baseline,
        devices=devices,
        staff=staff,
        companion_map=companion_map,
        shows=shows,
        multiview=multiview,
    )


def example_site_dir() -> Path:
    return default_config_dir().parent / "site" / "example"
