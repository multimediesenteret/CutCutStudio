# `installer/` – installasjon på regi-PC-en

| Fil | Innhold |
| --- | --- |
| `install-services.ps1` | Installerer Windows-tjenesten `CutCut` (og valgfritt `CutCut-Companion`) med WinSW 2.12. WinSW-filen sjekkes mot SHA-256. Kan kjøres på nytt, og `-Uninstall` fjerner tjenestene. `-DryRun` viser hva skriptet ville gjort |
| `winsw/CutCut.xml.tmpl` | Tjenesten som starter `cutcut supervisor`. Den starter automatisk med Windows, og etter krasj på nytt etter 5, 10 og 30 s. Loggene ruller i `data\logs\service` |
| `winsw/Companion.xml.tmpl` | Companion som tjeneste. Stien og argumentene bekreftes på test-PC-en (Q35) |

Pakke-bygg og `install.ps1` med tilbakerulling kommer i SO-3 og SO-4. Til da kjøres CutCut fra en mappe med `uv sync`. Veiledningen står i `docs/studio/tjenester.md`.

CI-jobben `windows-service` installerer den ekte tjenesten på en Windows-maskin og sjekker tre ting:
- at den starter;
- at en `core` som drepes, kommer tilbake;
- at ingen prosesser blir igjen når tjenesten stoppes.
