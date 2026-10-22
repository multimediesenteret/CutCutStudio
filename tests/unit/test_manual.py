"""The manual (docs/manual) is kept current: the PDF is built from README.md with
`pnpm manual`, which writes a hash of its inputs. Changing the manual without building the
PDF again fails here (AGENTS.md 8)."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANUAL = ROOT / "docs" / "manual"
INPUTS = [
    MANUAL / "README.md",
    MANUAL / "oppsett.png",
    ROOT / "tools" / "manual" / "template.html",
    ROOT / "tools" / "manual" / "cover.html",
]


def test_the_manual_pdf_is_built_from_the_current_source() -> None:
    h = hashlib.sha256()
    for f in INPUTS:
        h.update(f.read_bytes())
    recorded = (MANUAL / "kilde.sha256").read_text(encoding="utf-8").strip()
    assert recorded == h.hexdigest(), (
        "docs/manual er endret uten at PDF-en er bygget på nytt: kjør `pnpm manual`"
    )
    assert (MANUAL / "CutCut-Studio-manual.pdf").stat().st_size > 100_000


def test_every_chapter_of_the_manual_is_in_the_contents() -> None:
    build = (ROOT / "tools" / "manual" / "build.mjs").read_text(encoding="utf-8")
    text = (MANUAL / "README.md").read_text(encoding="utf-8")
    chapters = [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]
    missing = [c for c in chapters if f'"{c}"' not in build]
    assert not missing, f"Legg kapitlene inn i GROUPS i tools/manual/build.mjs: {missing}"
