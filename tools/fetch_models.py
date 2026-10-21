"""Download the model files in models/manifest.yaml and verify their SHA-256.

    uv run python tools/fetch_models.py           # download what is missing
    uv run python tools/fetch_models.py --check   # only verify, exit 1 on a bad or missing file

A file with the wrong checksum is deleted, never used.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    manifest = YAML(typ="safe").load((MODELS / "manifest.yaml").read_text(encoding="utf-8"))
    ok = True
    for name, spec in manifest["models"].items():
        path = MODELS / name
        if not path.exists() and not args.check:
            print(f"laster ned {name}")
            urllib.request.urlretrieve(spec["url"], path)  # noqa: S310 - fixed https URL
        if not path.exists():
            print(f"MANGLER {name}")
            ok = False
            continue
        if sha256(path) != spec["sha256"]:
            print(f"FEIL SJEKKSUM {name}: slettet")
            path.unlink()
            ok = False
            continue
        print(f"ok {name}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
