"""Command line entry point: ``uv run cutcut``.

Sub-commands are added as the modules are built.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from cutcut import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cutcut", description="CutCut Studio")
    parser.add_argument("--version", action="version", version=f"cutcut {__version__}")
    sub = parser.add_subparsers(dest="command")

    sim = sub.add_parser(
        "sim",
        help="kjør motor, simulator og begge skjermer lokalt (ingen ekte utstyr)",
        description="Starter studioet på simulert utstyr. Åpne /touch/ og /tech/ i nettleseren.",
    )
    sim.add_argument("--host", default="127.0.0.1", help="adresse (standard 127.0.0.1)")
    sim.add_argument("--port", type=int, default=8080, help="port (standard 8080)")
    sim.add_argument("--seed", type=int, default=1, help="frø for syntetisk samtale")
    sim.add_argument("--ui-dir", type=Path, default=None, help="bygde skjermer (ui/dist)")
    sim.add_argument(
        "--site",
        type=Path,
        default=None,
        help="studio-oppsett, f.eks. site/multimediesenteret (standard: det fiktive site/example)",
    )
    sim.add_argument(
        "--smoke", action="store_true", help="start, sjekk helse og skjermer, avslutt (CI)"
    )
    sim.add_argument(
        "--vision", action="store_true", help="tegnet videolag: kamerabilder i teknikervinduet"
    )
    sim.add_argument(
        "--cameras",
        action="store_true",
        help="falske PTZ-kameraer bak den ekte kameravakten (utsnitt, zoom, AI-tracking)",
    )

    core = sub.add_parser(
        "core",
        help="kjør studioet med ekte utstyr (Companion, ATEM via atem-bridge, Pearl, lyd)",
        description="Startes av supervisor i studio. Skjermene på /touch/ og /tech/.",
    )
    core.add_argument(
        "--site", type=Path, required=True, help="studio-oppsett, f.eks. site/multimediesenteret"
    )
    core.add_argument("--data", type=Path, default=None, help="database og logger")
    core.add_argument("--host", default="127.0.0.1")
    core.add_argument("--port", type=int, default=8080)
    core.add_argument("--ui-dir", type=Path, default=None, help="bygde skjermer (ui/dist)")

    sup = sub.add_parser(
        "supervisor",
        help="start core, atem-bridge og lyd, og start dem på nytt når de faller ut (SO-1)",
        description="Kjøres som tjeneste i studio. Status vises under Helse i teknikervinduet.",
    )
    sup.add_argument("--site", type=Path, required=True, help="studio-oppsett")
    sup.add_argument("--data", type=Path, default=None, help="database og logger")
    sup.add_argument("--port", type=int, default=8080, help="porten core lytter på")
    sup.add_argument("--ui-dir", type=Path, default=None, help="bygde skjermer (ui/dist)")
    sup.add_argument("--audio-wav", type=Path, default=None, help="lyd fra fil til AU-5")

    audio = sub.add_parser(
        "audio",
        help="kjør audio-capture: mikrofoner til målinger på bussen (ADR-0014)",
        description="Leser multitrack fra RØDECaster (eller en WAV-fil) og sender audio.frame.",
    )
    audio.add_argument("--wav", type=Path, help="spill av en 48 kHz multitrack-WAV (fake)")
    audio.add_argument("--vad-model", type=Path, default=None, help="Silero VAD (.onnx)")
    audio.add_argument(
        "--site", type=Path, default=None, help="studio-oppsett (lekkasje fra baseline.yaml)"
    )

    pages = sub.add_parser(
        "companion-pages",
        help="lag Companion-sidene 10 og 11 og variablene som importfiler (DA-9)",
        description="Skriver tre .companionconfig-filer fra studio-oppsettet.",
    )
    pages.add_argument("--site", type=Path, required=True, help="studio-oppsett")
    pages.add_argument(
        "--out", type=Path, default=None, help="mappe (standard: equipment/companion)"
    )
    pages.add_argument(
        "--check", action="store_true", help="skriv ingenting; feil hvis filene er utdaterte"
    )

    vis = sub.add_parser(
        "vision",
        help="kjør videolaget: multiview inn, målinger per rute på bussen (VI-1)",
        description="Leser multiviewen fra capture-kortet (DeckLink, D-062) eller en fil og "
        "deler den i ruter. Kortet velges med `video` i devices.yaml.",
    )
    vis.add_argument("--site", type=Path, required=True, help="studio-oppsett (rutekartet)")
    vis.add_argument(
        "--device", type=int, default=None, help="capture-enhet etter nummer (overstyrer navnet)"
    )
    vis.add_argument("--file", type=Path, default=None, help="videofil i stedet for enhet")
    vis.add_argument("--synthetic", action="store_true", help="tegnet multiview (demo, test)")

    hw = sub.add_parser(
        "hwtest",
        help="maskintest på test-PC eller i studio, med rapport (AU-6, DA-5, CA-5, VI-4)",
        description="Følg instruksjonene. Rapporten (Markdown) limes inn i GitHub-issuet.",
    )
    hw.add_argument(
        "what",
        choices=["audio", "atem", "camera", "vision"],
        help="audio: RØDECaster (AU-6); atem: ATEM og Companion (DA-5); camera: PTZ (CA-5); "
        "vision: capture-kortet, DeckLink (VI-4)",
    )
    hw.add_argument("--site", type=Path, default=None, help="studio-oppsett")
    hw.add_argument(
        "--minutes", type=float, default=60.0, help="stabilitetstest (audio, vision; standard 60)"
    )
    hw.add_argument("--out", type=Path, default=None, help="mappe for rapporten")
    hw.add_argument("--save-wav", action="store_true", help="lagre lyden fra mic 1 i A2")
    hw.add_argument(
        "--api", default=None, help="CutCut som kjører (atem, vision; standard 127.0.0.1)"
    )
    hw.add_argument(
        "--user", default=None, help="teknikerens brukernavn (atem; vision: med forsinkelsestest)"
    )
    hw.add_argument("--camera", default=None, help="kameraet som testes, f.eks. C2 (camera)")
    hw.add_argument(
        "--device",
        type=int,
        default=None,
        help="capture-enhet etter nummer (vision; standard: kortet i devices.yaml etter navn)",
    )

    trace = sub.add_parser(
        "trace",
        help="skriv simulerte forløp som JSON for web-simulatoren (Vercel)",
        description="Kjører motoren på falsk klokke og lagrer alt skjermene ville fått.",
    )
    trace.add_argument("--out", type=Path, default=None, help="mappe (standard: simulatorens)")
    trace.add_argument(
        "--check", action="store_true", help="skriv ingenting; feil hvis forløpene er utdaterte"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "sim":
        from cutcut.sim.serve import SimOptions, default_ui_dir, serve, smoke

        opts = SimOptions(
            host=args.host,
            port=args.port,
            seed=args.seed,
            ui_dir=args.ui_dir or default_ui_dir(),
            site_dir=args.site,
            vision=args.vision,
            cameras=args.cameras,
        )
        return smoke(opts) if args.smoke else serve(opts)
    if args.command == "core":
        from cutcut.app.core import CoreOptions, default_data_dir
        from cutcut.app.core import serve as serve_core
        from cutcut.common.platform import get_platform
        from cutcut.sim.serve import default_ui_dir as ui_default

        return serve_core(
            CoreOptions(
                site_dir=args.site,
                data_dir=args.data or default_data_dir(),
                secrets=get_platform().secrets,
                host=args.host,
                port=args.port,
                ui_dir=args.ui_dir or ui_default(),
            )
        )
    if args.command == "supervisor":
        from cutcut.app.core import default_data_dir
        from cutcut.supervisor.main import SupervisorOptions
        from cutcut.supervisor.main import run as run_supervisor

        return run_supervisor(
            SupervisorOptions(
                site_dir=args.site.resolve(),
                data_dir=(args.data or default_data_dir()).resolve(),
                port=args.port,
                ui_dir=args.ui_dir,
                audio_wav=args.audio_wav,
            )
        )
    if args.command == "audio":
        from cutcut.audio.main import main as audio_main

        return audio_main(args.wav, args.vad_model, args.site)
    if args.command == "vision":
        from cutcut.vision.main import main as vision_main

        return vision_main(args.site, args.device, args.file, args.synthetic)
    if args.command == "hwtest":
        from cutcut.app.core import default_data_dir

        out = args.out or default_data_dir() / "hwtest"
        if args.what == "atem":
            from cutcut.hwtest.atem import main as atem_test

            if args.site is None:
                parser.error("hwtest atem trenger --site")
            return atem_test(args.site, args.api, args.user, out)
        if args.what == "vision":
            from cutcut.hwtest.vision import main as vision_test

            if args.site is None:
                parser.error("hwtest vision trenger --site")
            return vision_test(args.site, args.device, args.minutes, out, args.api, args.user)
        if args.what == "camera":
            from cutcut.hwtest.camera import main as camera_test

            if args.site is None or args.camera is None:
                parser.error("hwtest camera trenger --site og --camera")
            return camera_test(args.site, args.camera, out, None)
        from cutcut.hwtest.audio import main as audio_test

        return audio_test(args.site, args.minutes, out, args.save_wav)
    if args.command == "companion-pages":
        from cutcut.common.config import load_site
        from cutcut.devices.companion.pages import default_out
        from cutcut.devices.companion.pages import write as write_pages

        site = load_site(args.site)
        out = args.out or default_out(site)
        changed = write_pages(site, out, check=args.check)
        if args.check:
            if changed:
                print("Utdaterte Companion-filer: " + ", ".join(changed))
                return 1
            print("Companion-filene er oppdatert.")
            return 0
        print(f"Skrev i {out}: {', '.join(changed) or 'ingen endringer'}")
        return 0
    if args.command == "trace":
        from cutcut.sim.trace import default_trace_dir, write_all

        out = args.out or default_trace_dir()
        changed = write_all(out, check=args.check)
        if args.check and changed:
            print("Utdaterte forløp (kjør «uv run cutcut trace»): " + ", ".join(changed))
            return 1
        print(
            "Forløpene er oppdatert."
            if args.check
            else f"Skrev: {', '.join(changed) or 'ingen endringer'}"
        )
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
