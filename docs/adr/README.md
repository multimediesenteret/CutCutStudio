# Arkitekturbeslutninger

| ADR | Beslutning | Status |
| --- | --- | --- |
| [ADR-0001](0001-en-windows-pc.md) | Én Windows 11-PC kjører alt: motor, Companion, touch-skjerm og teknikervindu | Akseptert |
| [ADR-0002](0002-python-uv-strenge-typer.md) | Python 3.12 med strenge typer (mypy strict, Pydantic v2); avhengigheter låst med uv; egen Python i app-mappen | Akseptert |
| [ADR-0003](0003-tre-prosesser-supervisor.md) | Tre prosesser (core, vision, stt) under en supervisor som kjører som Windows-tjeneste (WinSW) | Akseptert, utvides av 0012/0014 |
| [ADR-0004](0004-avstemmingsslokke.md) | Avstemmingssløyfe: hvert sekund sammenlignes ønsket og faktisk tilstand for ATEM, Pearl og kameraer | Akseptert |
| [ADR-0005](0005-idempotente-kommandoer.md) | Alle enhetskommandoer er idempotente, har tidsavbrudd, går gjennom kø per enhet og har kretsbryter | Akseptert |
| [ADR-0006](0006-yaml-sqlite-jsonl.md) | Oppsett som YAML i git med skjema; kjøredata i SQLite (WAL); logg som JSON-linjer | Akseptert |
| [ADR-0007](0007-react-edge-kiosk.md) | Grensesnitt i React + TypeScript, servert lokalt; touch-skjermen i Edge kiosk-modus med tilordnet tilgang | Akseptert |
| [ADR-0008](0008-twn3-com-modus.md) | Kortleser (ELATEC TWN3) i virtuell COM-port-modus, ikke som tastatur | Akseptert |
| [ADR-0009](0009-kutt-via-companion.md) | Kutt og layouter går via Companion; ATEM leses direkte | Akseptert |
| [ADR-0010](0010-monoton-klokke.md) | Monoton klokke i motoren, NTP for veggklokke | Akseptert |
| [ADR-0011](0011-brytere-i-sanntid.md) | Brytere kan endres i sanntid fra teknikervinduet | Akseptert |
| [ADR-0012](0012-atem-bridge-node.md) | En egen liten prosess, atem-bridge, i Node.js med atem-connection, som snakker med regi-core over den interne meldingsbussen | Forslag |
| [ADR-0013](0013-web-simulator.md) | Web-simulator med samme GUI, publisert på Vercel | Forslag |
| [ADR-0014](0014-audio-capture-prosess.md) | Lyd via RØDE ASIO i egen prosess `audio-capture` | Forslag |

Spesifikasjonen 0.3 skriver `ADR-01`–`ADR-11`; de er de samme som filene `ADR-0001`–`ADR-0011`. `ADR-12` i spesifikasjonen 13.4 er `ADR-0012`.

Nye beslutninger får neste nummer. Gamle filer endres ikke; de settes til «Erstattet av ADR-NNNN». Mal: `template.md`.
