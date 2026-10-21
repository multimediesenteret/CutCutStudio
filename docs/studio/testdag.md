# Første dag på test-PC-en (M2)

Rekkefølgen for å få CutCut opp på test-PC-en, og deretter i studio. Hvert steg har en sjekk eller en rapport som limes inn i GitHub-issuet. Ingenting her endrer ATEM, Pearl eller RØDECaster uten at du bekrefter det.

| # | Gjør | Kommando eller sted | Rapport til |
| --- | --- | --- | --- |
| 1 | Windows-oppsett: først sjekk, så rett | `installer\setup-pc.ps1`, deretter `-Fix -NtpServer … -VersionsYaml C:\CutCut\site\equipment\versions.yaml` | SO-5 (#102) |
| 2 | Kode, avhengigheter og skjermer | `docs/studio/tjenester.md`, «Første installasjon» | – |
| 3 | Studio-oppsettet: IP-adresser fra IP-planen | `C:\CutCut\site\devices.yaml`, eller senere i Oppsett | Q20, Q37 |
| 4 | Passord i Credential Manager | `pearl_password`, `operator_pin`, `admin_pin` | – |
| 5 | Tjenesten CutCut | `installer\install-services.ps1 -Root C:\CutCut -UiDir …`. Start Windows på nytt: tjenesten skal starte selv | SO-2 (#101) |
| 6 | Kiosk og touch | `installer\kiosk\setup-kiosk.ps1 -Password … -AutoLogon`. Start på nytt, og lukk Edge: den skal komme tilbake | SO-6 (#103) |
| 7 | Companion-sidene | `docs/studio/companion.md`. Helse → `H-COMP-1` skal vise «sider v1» | DA-9 (#92) |
| 8 | Lyd | `uv run cutcut hwtest audio --site C:\CutCut\site` (ca. 70 min) | AU-6 (#83), Q21, Q24 |
| 9 | ATEM og Companion | `uv run cutcut hwtest atem --site C:\CutCut\site --user …` | DA-5 (#89), Q7 |
| 10 | Mikrofonene: lekkasje og støy | Teknikervinduet → Oppsett → Mikrofoner · steg 5. Lagre som fasit | AU-7 (#84) |
| 11 | Helse | Teknikervinduet → Helse: alle sjekker grønne, eller forklart | HS-2 (#98) |
| 12 | Første klipping via preview | En prøve med to personer, AUTO på. Operatøren vurderer | DA-6 (#90), T-M2 (#105) |

## Hvis noe går galt

- **Ingen lyd:** Helse viser `H-AUD-1` med grunnen fra `audio-capture`. Vanligst: ASIO-driveren mangler, eller RØDECaster står ikke i multitrack-modus.
- **ATEM svarer ikke:** sjekk IP under Oppsett, og at `atem-bridge` kjører under Helse → Prosesser. Er ATEM-adressen endret, startes `atem-bridge` på nytt neste gang supervisor starter den.
- **Touch er svart:** kiosk-vakten starter Edge på nytt etter 30 s. Loggen ligger i `C:\Users\cutcut-kiosk\AppData\Local\CutCut\kiosk-vakt.log`.
- **Feilsøkingspakke:** teknikervinduet → Logg → «Feilsøkingspakke». Den har ingen passord, og den legges ved issuet.
