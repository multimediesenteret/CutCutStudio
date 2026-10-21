# `installer/` – installasjon på regi-PC-en

| Fil | Innhold |
| --- | --- |
| `install-services.ps1` | Installerer Windows-tjenesten `CutCut` (og valgfritt `CutCut-Companion`) med WinSW 2.12. WinSW-filen sjekkes mot SHA-256. Kan kjøres på nytt, og `-Uninstall` fjerner tjenestene. `-DryRun` viser hva skriptet ville gjort |
| `winsw/CutCut.xml.tmpl` | Tjenesten som starter `cutcut supervisor`. Den starter automatisk med Windows, og etter krasj på nytt etter 5, 10 og 30 s. Loggene ruller i `data\logs\service` |
| `kiosk/setup-kiosk.ps1` | Kiosk-brukeren, automatisk innlogging og oppgaven som starter kiosk-vakten (SO-6, `docs/studio/kiosk.md`) |
| `kiosk/kiosk-vakt.ps1` | Holder Edge med touch-siden i gang. Starter Edge på nytt når den er borte, eller når siden ikke har sendt hjerteslag på 30 s |
| `winsw/Companion.xml.tmpl` | Companion som tjeneste. Stien og argumentene bekreftes på test-PC-en (Q35) |

Pakke-bygg og `install.ps1` med tilbakerulling kommer i SO-3 og SO-4. Til da kjøres CutCut fra en mappe med `uv sync`. Veiledningen står i `docs/studio/tjenester.md`.

CI-jobben `windows-service` installerer den ekte tjenesten på en Windows-maskin og sjekker tre ting:
- at den starter;
- at en `core` som drepes, kommer tilbake;
- at ingen prosesser blir igjen når tjenesten stoppes.

`setup-pc.ps1` sjekker Windows-oppsettet i spesifikasjonen 9.2 (SO-5), og retter det med `-Fix`.
- **Retter:** strøm, USB-strømsparing, rask oppstart, skjermsparer, Windows Update-tider, tidstjeneste (NTP) og brannmur for port 8080.
- **Bare sjekker:** fast IP, tjenester og kiosk, drivere (`-VersionsYaml` skriver dem til `equipment/versions.yaml`) og UPS. BIOS står som et punkt å sjekke for hånd.
- **Rapport:** som maskintestene.

CI kjører skriptet på Windows to ganger: én sjekk, og én gang med `-Fix`.
