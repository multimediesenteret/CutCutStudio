"""Build the Windows package for the studio PC (SO-3, plan supervisor-ops 2, spec 12.3).

    uv run python tools/build_bundle.py --version 1.0.0 --python <dir> --node <node.exe> \\
        --bridge <dir> --out dist

One folder, zipped, that runs without anything else installed on the PC:

    cutcut-<version>/
      python/          Python 3.12 (python-build-standalone) with the locked dependencies
      src/cutcut/      CutCut itself; python/…/site-packages/cutcut.pth points here
      node/node.exe    Node for atem-bridge
      bridges/atem/    atem-bridge with its production node_modules (``pnpm deploy``)
      ui/dist/         the built screens
      config/ models/ installer/ site/example/
      BUILD.json       version, commit, time, Python and Node versions
      sbom/            CycloneDX 1.5 for Python and Node

The layout mirrors the repository, so paths that CutCut finds relative to its source (config,
models, ui/dist, bridges/atem) work unchanged. Next to the zip: ``<zip>.sha256``. Built by CI
on a tag (``.github/workflows/release.yml``); install with ``installer/install.ps1``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", ".mypy_cache")
EXTRAS = ("silero", "vision")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], cwd: Path | None = None) -> str:
    """Our own build commands (uv, pip, git, the bundled Python): never outside input."""
    print("$", " ".join(cmd), flush=True)
    res = subprocess.run(cmd, check=True, text=True, capture_output=True, cwd=cwd)  # noqa: S603
    return res.stdout


def python_exe(pydir: Path) -> Path:
    win = pydir / "python.exe"
    return win if win.exists() else pydir / "bin" / "python3"


def site_packages(py: Path) -> Path:
    out = run([str(py), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"])
    return Path(out.strip())


def requirements(out: Path) -> Path:
    """The locked runtime dependencies, with hashes (no dev tools, no CutCut itself)."""
    req = out / "requirements.txt"
    cmd = ["uv", "export", "--frozen", "--no-dev", "--no-emit-project", "-o", str(req)]
    for extra in EXTRAS:
        cmd += ["--extra", extra]
    run(cmd, cwd=ROOT)
    return req


# --- SBOM ----------------------------------------------------------------------------------


def _bom(name: str, version: str, components: list[dict[str, str]]) -> dict[str, object]:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "component": {"type": "application", "name": name, "version": version},
        },
        "components": sorted(components, key=lambda c: (c["name"].lower(), c["version"])),
    }


def python_components(site: Path) -> list[dict[str, str]]:
    """Every installed distribution, from its ``*.dist-info/METADATA``."""
    out = []
    for meta in site.glob("*.dist-info/METADATA"):
        fields: dict[str, str] = {}
        for line in meta.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line:
                break
            key, _, value = line.partition(": ")
            if key in ("Name", "Version", "License-Expression", "License") and key not in fields:
                fields[key] = value.strip()
        if "Name" in fields and "Version" in fields:
            comp = {
                "type": "library",
                "name": fields["Name"],
                "version": fields["Version"],
                "purl": f"pkg:pypi/{fields['Name'].lower()}@{fields['Version']}",
            }
            lic = fields.get("License-Expression") or fields.get("License")
            if lic and len(lic) < 80:
                comp["licenses"] = [{"expression": lic}]  # type: ignore[assignment]
            out.append(comp)
    return out


def _package_root(pkg: Path) -> bool:
    parent = pkg.parent.parent
    return parent.name == "node_modules" or (
        parent.name.startswith("@") and parent.parent.name == "node_modules"
    )


def node_components(node_modules: Path) -> list[dict[str, str]]:
    """Every package under ``node_modules`` (pnpm's ``.pnpm`` store included), once each."""
    seen: dict[tuple[str, str], dict[str, str]] = {}
    for pkg in node_modules.rglob("package.json"):
        if not _package_root(pkg):
            continue  # a file inside a package (tests, fixtures), not the package itself
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name, version = data.get("name"), data.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            continue
        comp = {"type": "library", "name": name, "version": version}
        comp["purl"] = f"pkg:npm/{name.replace('@', '%40')}@{version}"
        lic = data.get("license")
        if isinstance(lic, str):
            comp["licenses"] = [{"expression": lic}]  # type: ignore[assignment]
        seen[(name, version)] = comp
    return list(seen.values())


# --- build ---------------------------------------------------------------------------------


def build(
    version: str, pydir: Path, node: Path, bridge: Path, out_dir: Path, ui: Path, models: Path
) -> Path:
    name = f"cutcut-{version}"
    dest = out_dir / name
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    # CutCut, config, models, installer and the screens, in the repository's layout
    shutil.copytree(ROOT / "src" / "cutcut", dest / "src" / "cutcut", ignore=IGNORE)
    shutil.copytree(ROOT / "config", dest / "config", ignore=IGNORE)
    shutil.copytree(ROOT / "installer", dest / "installer", ignore=IGNORE)
    # the fictional example studio: demo, simulator and the install smoke test. The real
    # studio setup lives next to the versions (C:\CutCut\site) and is never in the package.
    shutil.copytree(ROOT / "site" / "example", dest / "site" / "example", ignore=IGNORE)
    shutil.copytree(models, dest / "models", ignore=shutil.ignore_patterns("*.tmp"))
    if not (ui / "tech" / "index.html").exists():
        raise SystemExit(f"Skjermene er ikke bygget: {ui} (kjør pnpm build)")
    shutil.copytree(ui, dest / "ui" / "dist")
    for f in ("LICENSE", "NOTICE", "README.md", "CHANGELOG.md", "pyproject.toml", "uv.lock"):
        shutil.copy2(ROOT / f, dest / f)

    # atem-bridge with its production dependencies, and Node to run it
    if not (bridge / "node_modules").is_dir():
        raise SystemExit(f"atem-bridge mangler node_modules: {bridge} (pnpm deploy --prod)")
    if any(p.is_symlink() for p in (bridge / "node_modules").iterdir()):
        raise SystemExit("atem-bridge har lenkede node_modules; bruk --config.node-linker=hoisted")
    shutil.copytree(bridge, dest / "bridges" / "atem", symlinks=False)
    (dest / "node").mkdir()
    shutil.copy2(node, dest / "node" / node.name)

    # Python with the locked dependencies; CutCut itself through a .pth (relocatable)
    shutil.copytree(pydir, dest / "python", symlinks=True)
    for marker in (dest / "python").rglob("EXTERNALLY-MANAGED"):
        marker.unlink()  # uv marks its Pythons; this copy is CutCut's own
    py = python_exe(dest / "python")
    has_pip = subprocess.run([str(py), "-m", "pip", "--version"], capture_output=True)  # noqa: S603
    if has_pip.returncode:
        run([str(py), "-m", "ensurepip", "--default-pip"])
    req = requirements(out_dir)
    run([str(py), "-m", "pip", "install", "--no-deps", "--require-hashes", "--no-compile",
         "--disable-pip-version-check", "-r", str(req)])  # fmt: skip
    site = site_packages(py)
    rel = os.path.relpath(dest / "src", site)
    (site / "cutcut.pth").write_text(rel + "\n", encoding="utf-8")
    run([str(py), "-c", "import cutcut, fastapi, zmq, numpy; print(cutcut.__file__)"])

    # what is in it
    py_version = run([str(py), "-c", "import platform; print(platform.python_version())"]).strip()
    node_version = run([str(node), "--version"]).strip()
    commit = run(["git", "rev-parse", "HEAD"], cwd=ROOT).strip()
    build_info = {
        "version": version,
        "commit": commit,
        "built": datetime.now(UTC).isoformat(timespec="seconds"),
        "python": py_version,
        "node": node_version,
        "extras": list(EXTRAS),
    }
    (dest / "BUILD.json").write_text(json.dumps(build_info, indent=2) + "\n", encoding="utf-8")
    (dest / "sbom").mkdir()
    for kind, comps in (
        ("python", python_components(site)),
        ("node", node_components(dest / "bridges" / "atem" / "node_modules")),
    ):
        bom = _bom(f"cutcut-{kind}", version, comps)
        (dest / "sbom" / f"{name}-{kind}.cdx.json").write_text(
            json.dumps(bom, indent=2) + "\n", encoding="utf-8"
        )

    # zip and checksum
    zpath = out_dir / f"{name}-win64.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for path in sorted(dest.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(out_dir).as_posix())
    digest = sha256(zpath)
    (out_dir / f"{zpath.name}.sha256").write_text(f"{digest}  {zpath.name}\n", encoding="utf-8")
    for sb in (dest / "sbom").iterdir():
        shutil.copy2(sb, out_dir / sb.name)
    print(f"{zpath} · sha256 {digest}")
    return zpath


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--version", required=True, help="f.eks. 1.0.0 eller 1.0.0-rc.1 (uten v)")
    p.add_argument("--python", type=Path, required=True, help="python-build-standalone-mappe")
    p.add_argument("--node", type=Path, required=True, help="node.exe")
    p.add_argument(
        "--bridge",
        type=Path,
        required=True,
        help="atem-bridge fra «pnpm deploy --legacy --prod --config.node-linker=hoisted»",
    )
    p.add_argument("--out", type=Path, default=ROOT / "dist-bundle")
    p.add_argument("--ui", type=Path, default=ROOT / "ui" / "dist")
    p.add_argument("--models", type=Path, default=ROOT / "models")
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    build(a.version.removeprefix("v"), a.python, a.node, a.bridge, a.out, a.ui, a.models)
    return 0


if __name__ == "__main__":
    sys.exit(main())
