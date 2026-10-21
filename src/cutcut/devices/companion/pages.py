"""CutCut's Companion pages as import files (DA-9, spec 7.1, 7.2).

Three files, made from the studio setup so the buttons always match what the engine presses:

* ``cutcut-side-10.companionconfig`` – page 10 «REGI», pressed by the engine: row 0 puts a
  source on preview, rows 1–2 run the layout macros (7.2), row 3 is TAKE CUT / TAKE MIX.
* ``cutcut-side-11.companionconfig`` – page 11 «OPERATØR»: direct program cuts for
  emergencies (S5) and the «Kun lyd» graphic.
* ``cutcut-variabler.companionconfig`` – the custom variables the engine writes (``regi_*``)
  and ``cutcut_pages_version``, which ``H-COMP-1`` reads to know the right pages are in.

**Format.** Companion 4.3 export format (file version 12), which every Companion 5.x imports
and upgrades itself (button → layered button, module option upgrades). Options for the ATEM
module (``bmd-atem``) are written as its v3 module stored them (plain values, zero-based M/E,
1-based macro numbers); ``upgradeIndex`` 6 tells a newer module to run its own upgrades from
there. On import, Companion asks which of its connections is «ATEM»: pick the studio's ATEM.

Import pages into page 10 and 11 under *Import/Export → Buttons*, and the variables under
*Full import* with «Import, preserving unselected components» and only *Custom Variables*
ticked (docs/studio/companion.md). Verified in the studio by the machine test (DA-5).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from cutcut.common.config import Site
from cutcut.common.ids import SourceId
from cutcut.common.models.site import CompanionButton
from cutcut.devices.atem.bridge import MP1, SUPERSOURCE, site_input_map
from cutcut.devices.atem.macros import BY_SHOT, LAYOUT_RESET

FILE_VERSION: Final = 12  # Companion 4.3 / 5.0 export format
ATEM_CONNECTION: Final = "cutcut-atem"
ATEM_MODULE: Final = "bmd-atem"
ATEM_UPGRADE_INDEX: Final = 6  # last v3.x upgrade script in companion-module-bmd-atem
ME: Final = 0  # mix effect 1, zero-based as stored by the v3 module
GRID: Final = {"minColumn": 0, "maxColumn": 7, "minRow": 0, "maxRow": 3}  # Stream Deck XL

# Spec 7.2: layout macros, numbered as in ATEM Software Control (cutcut.devices.atem.macros).
LAYOUT_MACROS: Final[dict[str, int]] = dict(BY_SHOT)
LAYOUT_RESET_MACRO: Final = LAYOUT_RESET

ENGINE_VARIABLES: Final[dict[str, str]] = {
    "regi_shot": "Bildet motoren har valgt (f.eks. CU:P2)",
    "regi_rule": "Regelen bak siste beslutning (f.eks. T1)",
    "regi_reason": "Hvorfor, med ord",
    "regi_mode": "Motorens modus (N1–N4, NxC, A)",
    "regi_auto": "AUTO på eller av",
    "regi_health": "Helse: ok, warn eller error",
}

WHITE: Final = 0xFFFFFF
GREY: Final = 0x2B2F36
GREEN: Final = 0x1E6B3A
BLUE: Final = 0x23477A
RED: Final = 0x9B1C1C
ORANGE: Final = 0x8A5A00


@dataclass(frozen=True)
class Button:
    text: str
    action: str  # ATEM module action id
    options: dict[str, Any]
    bgcolor: int = GREY


def _short(source: SourceId) -> str:
    return {"C5": "BIRD", "LAPTOP": "LAPTOP", "SUPERSOURCE": "SUPER\\nSOURCE"}.get(
        source.value, source.value
    )


def _control(page: int, b: CompanionButton, button: Button) -> dict[str, Any]:
    """A Companion 4.3 ``button`` with one ATEM action on press."""
    action_id = f"cutcut-p{page}-r{b.row}-c{b.col}"
    return {
        "type": "button",
        "style": {
            "text": button.text,
            "textExpression": False,
            "size": "auto",
            "alignment": "center:center",
            "pngalignment": "center:center",
            "color": WHITE,
            "bgcolor": button.bgcolor,
            "show_topbar": "default",
            "png64": None,
        },
        "options": {"stepProgression": "auto", "rotaryActions": False},
        "feedbacks": [],
        "localVariables": [],
        "steps": {
            "0": {
                "action_sets": {
                    "down": [
                        {
                            "type": "action",
                            "id": action_id,
                            "definitionId": button.action,
                            "connectionId": ATEM_CONNECTION,
                            "options": button.options,
                            "upgradeIndex": ATEM_UPGRADE_INDEX,
                        }
                    ],
                    "up": [],
                },
                "options": {"runWhileHeld": []},
            }
        },
    }


def _page_file(page: int, name: str, buttons: dict[CompanionButton, Button]) -> dict[str, Any]:
    controls: dict[str, dict[str, Any]] = {}
    for b, button in sorted(buttons.items(), key=lambda kv: (kv[0].row, kv[0].col)):
        controls.setdefault(str(b.row), {})[str(b.col)] = _control(page, b, button)
    return {
        "version": FILE_VERSION,
        "type": "page",
        "companionBuild": None,
        "page": {"id": f"cutcut-page-{page}", "name": name, "controls": controls, "gridSize": GRID},
        "instances": {
            ATEM_CONNECTION: {
                "label": "ATEM",
                "moduleId": ATEM_MODULE,
                "lastUpgradeIndex": ATEM_UPGRADE_INDEX,
                "sortOrder": 0,
            }
        },
        "connectionCollections": [],
        "oldPageNumber": page,
    }


def engine_page(site: Site) -> dict[str, Any]:
    """Page 10 «REGI»: exactly the buttons ``companion_map.yaml`` says the engine presses."""
    cmap = site.companion_map
    inputs = {src: n for n, src in site_input_map(list(site.shows.values())).items()}
    buttons: dict[CompanionButton, Button] = {}
    for source, b in cmap.preview.items():
        n = inputs.get(source)
        if n is None:
            continue  # not wired in this studio; the engine never asks for it
        buttons[b] = Button(
            f"PRV\\n{_short(source)}", "preview", {"mixeffect": ME, "input": n}, GREEN
        )
    for shot, b in cmap.layouts.items():
        macro = LAYOUT_MACROS.get(shot)
        if macro is not None:
            label = shot.replace("PIP:", "").replace("+", " + ")
            buttons[b] = Button(label, "macrorun", {"macro": macro, "action": "run"}, BLUE)
    buttons[cmap.layout_off] = Button(
        "LAYOUT\\nAV", "macrorun", {"macro": LAYOUT_RESET_MACRO, "action": "run"}, BLUE
    )
    buttons[cmap.take_cut] = Button("TAKE\\nCUT", "cut", {"mixeffect": ME}, RED)
    buttons[cmap.take_mix] = Button("TAKE\\nMIX", "auto", {"mixeffect": ME}, RED)
    return _page_file(10, "CutCut REGI", buttons)


def operator_page(site: Site) -> dict[str, Any]:
    """Page 11 «OPERATØR»: direct program cuts and «Kun lyd» (media player 1)."""
    cmap = site.companion_map
    inputs = {src: n for n, src in site_input_map(list(site.shows.values())).items()}
    inputs[SourceId.SUPERSOURCE] = SUPERSOURCE
    buttons: dict[CompanionButton, Button] = {}
    for source, b in cmap.operator_direct.items():
        n = inputs.get(source)
        if n is not None:
            buttons[b] = Button(
                f"PGM\\n{_short(source)}", "program", {"mixeffect": ME, "input": n}, RED
            )
    if cmap.operator_audio_only is not None:
        buttons[cmap.operator_audio_only] = Button(
            "KUN\\nLYD", "program", {"mixeffect": ME, "input": MP1}, ORANGE
        )
    return _page_file(11, "CutCut OPERATØR", buttons)


def variables_file(site: Site) -> dict[str, Any]:
    """The custom variables, with ``cutcut_pages_version`` = the version core expects."""
    version = site.devices.companion.pages_version
    variables: dict[str, Any] = {
        name: {
            "description": text,
            "defaultValue": "",
            "persistCurrentValue": False,
            "sortOrder": i,
        }
        for i, (name, text) in enumerate(ENGINE_VARIABLES.items())
    }
    variables["cutcut_pages_version"] = {
        "description": "Versjonen av CutCut-sidene (side 10 og 11). Leses av helsesjekken H-COMP-1",
        "defaultValue": str(version),
        "persistCurrentValue": False,
        "sortOrder": len(variables),
    }
    return {
        "version": FILE_VERSION,
        "type": "full",
        "companionBuild": None,
        "custom_variables": variables,
        "customVariablesCollections": [],
    }


FILES: Final = {
    "cutcut-side-10.companionconfig": engine_page,
    "cutcut-side-11.companionconfig": operator_page,
    "cutcut-variabler.companionconfig": variables_file,
}


def render(site: Site) -> dict[str, str]:
    return {
        name: json.dumps(make(site), ensure_ascii=False, indent=1) + "\n"
        for name, make in FILES.items()
    }


def write(site: Site, out: Path, *, check: bool = False) -> list[str]:
    """Write the three files; with ``check`` only report which are out of date."""
    changed = []
    for name, text in render(site).items():
        path = out / name
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            changed.append(name)
            if not check:
                out.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    return changed


def default_out(site: Site) -> Path:
    return site.root / "equipment" / "companion"
