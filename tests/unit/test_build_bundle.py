"""SO-3: the SBOM parts of tools/build_bundle.py (the whole package is built and installed on
Windows in .github/workflows/release.yml)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_bundle", ROOT / "tools" / "build_bundle.py"
    )
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_bundle"] = mod
    spec.loader.exec_module(mod)
    return mod


bb = load()


def test_python_components_from_dist_info(tmp_path: Path) -> None:
    for name, version, lic in (("fastapi", "0.115.0", "MIT"), ("pyzmq", "26.2.0", None)):
        d = tmp_path / f"{name}-{version}.dist-info"
        d.mkdir()
        meta = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
        if lic:
            meta += f"License-Expression: {lic}\n"
        (d / "METADATA").write_text(meta + "\nLong description: Name: not-this\n")
    comps = {c["name"]: c for c in bb.python_components(tmp_path)}
    assert set(comps) == {"fastapi", "pyzmq"}
    assert comps["fastapi"]["purl"] == "pkg:pypi/fastapi@0.115.0"
    assert comps["fastapi"]["licenses"] == [{"expression": "MIT"}]
    assert "licenses" not in comps["pyzmq"]


def test_node_components_only_package_roots(tmp_path: Path) -> None:
    nm = tmp_path / "node_modules"

    def pkg(path: Path, name: str, version: str) -> None:
        path.mkdir(parents=True)
        (path / "package.json").write_text(json.dumps({"name": name, "version": version}))

    pkg(nm / "zeromq", "zeromq", "6.8.0")
    pkg(nm / "@scope" / "lib", "@scope/lib", "1.0.0")
    pkg(nm / "zeromq" / "node_modules" / "tslib", "tslib", "2.8.1")
    pkg(nm / "zeromq" / "test" / "fixture", "fixture", "0.0.0")  # inside a package: not one
    comps = {(c["name"], c["version"]) for c in bb.node_components(nm)}
    assert comps == {("zeromq", "6.8.0"), ("@scope/lib", "1.0.0"), ("tslib", "2.8.1")}
    scoped = next(c for c in bb.node_components(nm) if c["name"] == "@scope/lib")
    assert scoped["purl"] == "pkg:npm/%40scope/lib@1.0.0"


def test_bom_is_cyclonedx_1_5() -> None:
    bom = bb._bom(
        "cutcut-python",
        "1.0.0",
        [
            {"type": "library", "name": "b", "version": "1"},
            {"type": "library", "name": "A", "version": "1"},
        ],
    )
    assert (bom["bomFormat"], bom["specVersion"]) == ("CycloneDX", "1.5")
    assert [c["name"] for c in bom["components"]] == ["A", "b"]
