"""Rule traceability: rule ID → code → tests (spec 12.1).

    uv run python tools/traceability.py          # write docs/reference/{traceability,rules}.md
    uv run python tools/traceability.py --check  # fail if they are stale or a rule lacks tests

A rule counts as tested when a test function is named ``test_<ID>_…`` (e.g. ``test_T2_…``).
Rules that belong to later milestones are listed in ``PLANNED`` with the milestone; a rule in
``PLANNED`` that already has tests is an error too, so the list cannot go stale.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cutcut.common.config import load_rule_presets  # noqa: E402
from cutcut.common.ids import RuleId  # noqa: E402

OUT_TRACE = ROOT / "docs" / "reference" / "traceability.md"
OUT_RULES = ROOT / "docs" / "reference" / "rules.md"

# Rules implemented outside the engine or in later milestones (docs/plans/milestones.md).
PLANNED: dict[str, str] = {
    "PV2": "M3 – kameradrivere (GuardedCamera)",
    "PV3": "M4 – video_confirm",
    "S5": "M2 – Companion/ATEM-utfører",
    **{f"L{i}": "M4 – layouts" for i in range(1, 5)},
    **{f"R{i}": "M4 – reactions" for i in range(1, 4)},
    **{f"F{i}": "M4 – framing_variety" for i in range(1, 4)},
    **{f"Z{i}": "M4 – slow_zoom" for i in range(1, 4)},
    **{f"AT{i}": "M4 – ai_tracking" for i in range(1, 7)},
    **{f"V{i}": "M4 – video_confirm / reactions" for i in range(1, 7)},
}

TEST_RE = re.compile(r"^\s*(?:async\s+)?def (test_([A-Z]+[0-9]+)_\w*)\(", re.M)
CODE_RE = re.compile(r"RuleId\.([A-Z]+[0-9]+)\b")


def collect() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    tests: dict[str, list[str]] = {}
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        rel = path.relative_to(ROOT).as_posix()
        for match in TEST_RE.finditer(path.read_text(encoding="utf-8")):
            tests.setdefault(match.group(2), []).append(f"{rel}::{match.group(1)}")
    code: dict[str, list[str]] = {}
    for path in sorted((ROOT / "src").rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        for rule in sorted(set(CODE_RE.findall(path.read_text(encoding="utf-8")))):
            code.setdefault(rule, []).append(rel)
    return tests, code


def rule_ids() -> list[str]:
    return [r.value for r in RuleId if r is not RuleId.MANUAL]


def problems(tests: dict[str, list[str]], code: dict[str, list[str]]) -> list[str]:
    out = []
    for rid in rule_ids():
        if rid in PLANNED:
            if rid in tests:
                out.append(f"{rid} has tests but is still listed in PLANNED – remove it there")
            continue
        if rid not in tests:
            out.append(f"{rid} has no test named test_{rid}_…")
        if rid not in code:
            out.append(f"{rid} is not referenced in src/ (RuleId.{rid})")
    return out


def render_traceability(tests: dict[str, list[str]], code: dict[str, list[str]]) -> str:
    lines = [
        "# Sporbarhet: regel → kode → test",
        "",
        "Generert av `tools/traceability.py` (spesifikasjonen 12.1). Ikke rediger for hånd.",
        "",
        "| Regel | Status | Kode | Tester |",
        "| --- | --- | --- | --- |",
    ]
    for rid in rule_ids():
        status = f"Planlagt: {PLANNED[rid]}" if rid in PLANNED else "Implementert"
        files = ", ".join(f"`{f}`" for f in code.get(rid, [])) or "–"
        n = len(tests.get(rid, []))
        lines.append(f"| `{rid}` | {status} | {files} | {n} |")
    lines.append("")
    return "\n".join(lines)


def render_rules() -> str:
    presets = load_rule_presets()
    fields = list(type(presets.standard).model_fields)
    lines = [
        "# Regelverdier per forhåndsvalg",
        "",
        "Generert av `tools/traceability.py` fra `config/defaults/rules.yaml`.",
        "Ikke rediger for hånd.",
        "",
        "| Verdi | Rolig | Standard | Energisk |",
        "| --- | --- | --- | --- |",
    ]

    def fmt(v: object) -> str:
        if isinstance(v, bool):
            return "på" if v else "av"
        return f"{v:g}".replace(".", ",") if isinstance(v, float) else str(v)

    for name in fields:
        vals = [fmt(getattr(getattr(presets, p), name)) for p in ("rolig", "standard", "energisk")]
        lines.append(f"| `{name}` | {' | '.join(vals)} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    tests, code = collect()
    outputs = {OUT_TRACE: render_traceability(tests, code), OUT_RULES: render_rules()}
    errors = problems(tests, code)
    if args.check:
        for path, content in outputs.items():
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                errors.append(f"{path.relative_to(ROOT)} is stale; run tools/traceability.py")
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1 if errors else 0
    OUT_TRACE.parent.mkdir(parents=True, exist_ok=True)
    for path, content in outputs.items():
        path.write_text(content, encoding="utf-8")
        print(path.relative_to(ROOT))
    for err in errors:
        print(f"WARNING: {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
