from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from cutcut.common.config import (
    ConfigError,
    RuleParams,
    default_config_dir,
    effective_rules,
    load_rule_presets,
    load_show,
    load_show_types,
    migrate,
)
from cutcut.common.config.schema import SCHEMAS, render

FIXTURES = Path(__file__).parents[2] / "fixtures"


def test_rule_presets_load_and_standard_matches_spec() -> None:
    presets = load_rule_presets()
    std = presets.standard
    # spot-check against spec 5.3, 5.10, 5.11
    assert (std.T1_vad_threshold, std.T1_dominance_db, std.T2_confirm_ms) == (0.6, 6, 800)
    assert (std.T3_min_shot_s, std.T8_silence_s, std.T12_host_weight) == (2.5, 3, 1.1)
    assert (std.K1_pause_ms, std.K3_max_wait_s, std.H2_no_return_s) == (300, 1.5, 4)


def test_presets_are_ordered_calm_to_energetic() -> None:
    p = load_rule_presets()
    assert p.rolig.T2_confirm_ms > p.standard.T2_confirm_ms > p.energisk.T2_confirm_ms
    assert p.rolig.T3_min_shot_s > p.standard.T3_min_shot_s > p.energisk.T3_min_shot_s
    assert p.rolig.H2_no_return_s > p.standard.H2_no_return_s > p.energisk.H2_no_return_s


def test_s3_can_never_go_below_one_second() -> None:
    data = load_rule_presets().standard.model_dump()
    data["S3_min_cut_gap_s"] = 0.5
    with pytest.raises(ValueError, match="greater than or equal to 1"):
        RuleParams.model_validate(data)


def test_show_overrides_apply() -> None:
    show = load_show(FIXTURES / "spec_show_example.yaml")
    rules = effective_rules(show, load_rule_presets())
    assert rules.T7_reaction_after_s == 18  # from rules_override in the spec example
    assert rules.T2_confirm_ms == 800


def test_unknown_override_is_refused(tmp_path: Path) -> None:
    data: dict[str, Any] = YAML(typ="safe").load(FIXTURES / "spec_show_example.yaml")
    data["rules_override"] = {"T99_nonsense": 1}
    path = tmp_path / "show.yaml"
    YAML(typ="safe").dump(data, path)
    show = load_show(path)
    with pytest.raises(ConfigError, match="T99_nonsense"):
        effective_rules(show, load_rule_presets())


def test_newer_schema_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "show.yaml"
    path.write_text("schema_version: 99\nid: x\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="nyere"):
        load_show(path)


def test_migration_chain_runs_in_order() -> None:
    steps = {
        1: lambda d: {**d, "a": 1},
        2: lambda d: {**d, "b": d["a"] + 1},
    }
    assert migrate({"schema_version": 1}, 3, steps, "test") == {"schema_version": 3, "a": 1, "b": 2}
    with pytest.raises(ConfigError, match="mangler migrering"):
        migrate({"schema_version": 1}, 3, {1: steps[1]}, "test")


def test_broken_yaml_gives_readable_error(tmp_path: Path) -> None:
    path = tmp_path / "show.yaml"
    path.write_text("id: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="ugyldig YAML"):
        load_show(path)


def test_missing_file_gives_readable_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="finnes ikke"):
        load_show(tmp_path / "nope.yaml")


def test_show_types_default_is_podcast_and_audio_only_exists() -> None:
    types = load_show_types()
    key, default = types.get(None)
    assert key == "podcast"
    assert default.rules_preset == "standard"
    assert types.get("kun-lyd")[1].audio_only
    with pytest.raises(ConfigError):
        types.get("nope")


@pytest.mark.parametrize("name", sorted(SCHEMAS))
def test_generated_schema_is_up_to_date(name: str) -> None:
    committed = (default_config_dir() / "schema" / name).read_text(encoding="utf-8")
    assert committed == render(SCHEMAS[name]), (
        f"config/schema/{name} is stale; run: uv run python -m cutcut.common.config.schema"
    )
