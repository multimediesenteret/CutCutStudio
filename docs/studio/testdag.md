# Studioperioden: sjekkliste

Én plan for hele perioden i studio (P9 i [`for-studio.md`](../plans/for-studio.md)). Alt som kunne lages og prøves uten studio, er gjort før. Perioden brukes til tre ting: **maskintester**, **kalibrering** og **prøving** (grunnmodus først, så bryterne én og én).

Hvert punkt sier hva som gjøres, hvordan, og når det er godkjent. Rapporter fra maskintestene limes inn i issuet som står i siste kolonne. Ingenting her endrer ATEM, Pearl eller RØDECaster uten at du bekrefter det.

Rekkefølgen er viktig: hver del bygger på den forrige. Blokk 0 gjøres hjemme, før perioden. Blokk 1–3 tar normalt første og andre dag. 72-timerstesten (blokk 6) startes så tidlig som mulig, og går mens resten prøves.

## 0. Før perioden

| # | Gjør | Hvordan | Godkjent når |
| --- | --- | --- | --- |
| 0.1 | Siste versjon bygget og prøvd | CI grønn på `main`; `uv run cutcut sim --site site\example --smoke` | Røyktesten er grønn |
| 0.2 | Modellene lastet ned | `uv run python tools/fetch_models.py` (YuNet til ansikt) | Ingen feil; filene ligger i `models\` |
| 0.3 | Studio-oppsettet klart | `C:\CutCut\site\devices.yaml` med IP-er fra IP-planen, og inngangskartet (kamera 1 = vert, kamera 2 = gjest 1 osv.) | Q20 og Q37 besvart |
| 0.4 | Med til studio | Gråkort, lagringsdisk til opptakene (Q1), samtykkeskjema, utskrift av denne lista | – |
| 0.5 | Deltakere booket | Tre testsendinger på 20–30 min: én med 1 person, én med 2, én med 3–4 og laptop | Avtalt |

## 1. Rom, strøm, nett og PC

| # | Gjør | Hvordan | Godkjent når | Rapport |
| --- | --- | --- | --- | --- |
| 1.1 | UPS og strøm | Regi-PC, switch, ATEM og Pearl på UPS. Trekk strømmen til UPS-en i 1 min | Alt står; UPS-en varsler | – |
| 1.2 | Switch for utstyret | Uadministrert switch. ATEM, kameraer, Pearl og RØDECaster (om nett) kobles hit | Alle lyser på switchen | – |
| 1.3 | To nettverkskort | Kort 1 mot switchen (fast IP fra IP-planen, ingen gateway). Kort 2 mot campusnettet (DHCP) | Helse → `H-NET-1` og `H-NET-2` grønne | – |
| 1.4 | Windows | `installer\setup-pc.ps1`, så `-Fix -NtpServer … -VersionsYaml C:\CutCut\site\equipment\versions.yaml`. Servicevinduet settes etter vår egen plan | Sjekken er grønn | SO-5 (#102) |
| 1.5 | CutCut installert | `docs/studio/tjenester.md`, «Første installasjon». Passord i Credential Manager: `pearl_password`, `operator_pin`, `admin_pin` | `uv run cutcut --help` svarer | – |
| 1.6 | Tjenesten | `installer\install-services.ps1 -Root C:\CutCut -UiDir …`. Start Windows på nytt | Tjenesten starter selv; Helse → Prosesser viser alt i gang | SO-2 (#101) |
| 1.7 | Kiosk og touch | `installer\kiosk\setup-kiosk.ps1 -Password … -AutoLogon`. Vanlig touch-skjerm. Start på nytt og lukk Edge | Edge kommer tilbake av seg selv | SO-6 (#103) |
| 1.8 | Companion på samme PC | Installer Companion, importer sidene (`docs/studio/companion.md`) | Helse → `H-COMP-1` viser «sider v1» | DA-9 (#92) |
| 1.9 | INOGENI 4KXUSB3, og ATEM-ens USB-C | INOGENI direkte i en USB 3-port på PC-en (ikke hub), multiview-utgangen fra ATEM inn på kortet, 1080p50. Koble også USB-C fra ATEM-en til en USB 3-port, og velg Output → Webcam Out → **Multi View** i ATEM Software Control (finnes valget på HD8 ISO? Noter i Q41). INOGENI er valgt under Oppsett, steg 6 | Helse → `H-VID-1` grønn | Q41 |
| 1.10 | Support-e-post | Teknikervinduet → Innstillinger → Varsling. Standard er eierens adresse | Vises på touch under «Hjelp» | – |
| 1.11 | Feilsøkingsmodus på | Teknikervinduet → Helse → Feilsøkingsmodus → **24 timer**. Slå den på igjen hver dag i perioden | «Feilsøking» vises øverst i teknikervinduet | – |

## 2. Maskintester

Kommandoene og stegene står i [`maskintest.md`](maskintest.md). Hver test skriver en rapport.

| # | Test | Kommando | Varighet | Rapport |
| --- | --- | --- | --- | --- |
| 2.1 | RØDECaster | `uv run cutcut hwtest audio --site C:\CutCut\site` | ca. 70 min | AU-6 (#83), Q21, Q24 |
| 2.2 | ATEM og Companion | `uv run cutcut hwtest atem --site C:\CutCut\site --user …` | 10 min | DA-5 (#89), Q7 |
| 2.3 | PTZ-kameraene, ett av gangen | `uv run cutcut hwtest camera --site C:\CutCut\site --camera C1` (så C2, C3 …) | 5 min per kamera | CA-5 (#142), Q16 |
| 2.4 | Multiview inn, A/B | Stopp `vision` under Helse → Prosesser, så `uv run cutcut hwtest vision --site C:\CutCut\site --user … --metode inogeni`, og det samme med `--metode atem_usb`. Start et ISO-opptak mens ATEM-en sender på USB-C. Velg metode i steg 6 ut fra resultatet | ca. 2 × 65 min | VI-4 (#136), Q41 |
| 2.5 | Pearl | `uv run cutcut hwtest pearl --site C:\CutCut\site --user …`. Ikke under et opptak | ca. 5 min | SE-3, 10.4 |

Fra 2.3 skrives to tall inn i oppsettet før bryterne prøves:

- **KA4** gir `Calibration` (enheter per 10°) per kamera.
- **KA5** gir laveste zoomfart. Er zoomen synlig rykkete eller for rask på lufta, settes `slow_zoom_speed` ned for det kameraet (`Z3`).

**KA7** svarer på Q16: følger OBSBOT-en med tracking på, og står den stille med tracking av? Svaret avgjør om `ai_tracking` prøves i blokk 5.

## 3. Setup-hjelperen, steg 1–10

Teknikervinduet → Oppsett. Hvert steg godkjennes i hjelperen når sjekkene er grønne.

| Steg | Hva | Godkjent når |
| --- | --- | --- |
| 1 Nett og IP | Adressene i Enheter stemmer med IP-planen | `H-NET-*`, `H-ATEM-1`, `H-COMP-1`, `H-PRL-1` og `H-CAM-C*` grønne |
| 2 PC og Windows | Strøm, søvn, oppdateringer, prioritet | `H-PC-*` og `H-PROC-*` grønne |
| 3 ATEM | Modell, 1080p50, innganger | `H-ATEM-1`, `-2`, `-4` og `H-VID-2` grønne |
| 4 Kameraer | Manuell hvitbalanse og eksponering. **Fargematching:** gråkort foran hvert kamera, velg referansekamera (normalt C1), trykk «Start fargematching» | Alle kameraer «like referansen» innen 5 runder. Kameraer på program eller preview hoppes over: ta dem av lufta og kjør igjen |
| 5 RØDECaster | Mikrofonene: lekkasje og støy, én og én | Lagret som fasit (AU-7, #84) |
| 6 Multiview | Rutekartet mot det ATEM viser | `H-VID-1`–`3` og `H-MV` grønne; hver rute viser riktig kamera |
| 7 Companion | Sidene og knappene | `H-COMP-1` grønn |
| 8 Makroer og grafikk | Layoutmakroene 10–40 (7.2) lages i ATEM; «Kun lyd»-grafikk | `H-ATEM-3` grønn |
| 9 Pearl | Opptak start og stopp fra touch og fra teknikervinduet | `H-PRL-1` grønn; status stemmer med Pearl |
| 10 Generalprøve | Alle sitter på sine plasser og snakker i 5 min, AUTO på | Kuttene ser riktige ut; avvik notert før godkjenning |

Når alle ti er godkjent: Helse → alle sjekker grønne, eller forklart (HS-2, #98).

## 4. Grunnmodus

Alle brytere **av**. Dette er sendingen slik den skal fungere fra første dag.

| # | Gjør | Hvordan | Godkjent når | Rapport |
| --- | --- | --- | --- | --- |
| 4.1 | Første klipping via preview | En prøve med to personer, AUTO på. Operatøren følger med | Operatøren godtar kuttene | DA-6 (#90), T-M2 (#105) |
| 4.2 | Tre testsendinger med opptak | Sendingene fra 0.5. Ta opp alt som står i [`opptak-og-klippeliste.md`](../intake/opptak-og-klippeliste.md): mic-spor, multiview, ISO, `meta.yaml`. Eksporter beslutningsloggen (Logg → CSV). Etter hver sending: `uv run cutcut hwtest akseptanse --since "<start>"` | Filene ligger på godkjent lagringssted; akseptanserapporten lagt i T-M3 | Q1, T-M3 |
| 4.3 | Ansikt på ekte bilde | `uv run cutcut hwtest faces --site C:\CutCut\site --file <multiview.mp4 fra 4.2>` | F1 minst 90 % brukbart per rute; F3 under 200 ms | P6 |
| 4.4 | Feil underveis | Under en prøvesending: drep `vision`, så `core` i Oppgavebehandling | Kuttingen fortsetter uten `vision`; `core` tilbake innen 5 s med samme oppsett | – |
| 4.5 | Lekkasje | Én person snakker høyt i 10 min | Ingen kutt til andre | – |
| 4.6 | Content | Koble til laptop, bytt slide, trekk ut kabelen | Slide vist innen 1 s; laptop ute av utvalget innen 1 s | – |
| 4.7 | Grafikk på lufta (P10) | Under en prøvesending: sett svart, så mediaspiller 2, så mediaspiller 1 med logoen på program fra ATEM-panelet. Så et kamera tilbake | AUTO venter mens grafikken står, Helse er grønn («annen kilde på lufta»); AUTO fortsetter 5 s etter at kameraet er tilbake | – |
| 4.8 | Opptak til justering (P11) | Før hver sending i 4.2: samtykke fra alle ([`samtykke-opptak.md`](../intake/samtykke-opptak.md)), feilsøkingsmodus på, RØDECaster multitrack-opptak til kort på, ATEM ISO på, multiview-opptak på. Etterpå: `uv run cutcut opptak importer --episode <navn> --samtykke --out D:\opptak --wav M1=… --wav M2=…`. Sjekk også at RØDECaster-en tar opp til kort mens CutCut får USB-lyden | Importen viser match over 0,6 for hver mikrofon og ingen OBS | Q1 |
| 4.9 | Sjekk dagens oppsett (P14) | Hver morgen i perioden: Helse → **Sjekk dagens oppsett**, med gråkort første dag. Sett én gang en gjest ved feil kamera og skru ned én fader | Grønt når alt er riktig; feil plass og nedskrudd fader meldes i navnerunden | – |

Klippelista (Q2) lages etterpå av en erfaren klipper, fra opptakene i 4.2.

## 5. Bryterne, én og én

Bare én bryter er på om gangen; de andre er av. Hver bryter går først i **skygge** (reglene logges, men kutter ikke), så **på**. Rekkefølgen under går fra det som påvirker minst til det som påvirker mest.

For hver bryter:

1. Teknikervinduet → Regi → sett bryteren til **Skygge**. Står den sperret, står grunnen der.
2. En prøvesending på 10 min med 2–3 personer.
3. Logg → **Skygge** viser hva bryteren ville gjort. Ser det fornuftig ut? Ville det gjort sendingen bedre? «Last ned CSV» har bryteren i egen kolonne.
4. Sett bryteren til **På**, og kjør en ny prøvesending på 10 min.
5. Skriv kort i issuet hva som virket og hva som bør justeres, og sett bryteren **av** før neste.

| # | Bryter | Forutsetning | Se spesielt etter |
| --- | --- | --- | --- |
| 5.1 | `layouts` (`L1`–`L4`) | Makroene 10–40 fra steg 8 | Bilde-i-bilde med laptop; firedelt med fire personer. `LAYOUT_RESET` hvis ATEM ikke bekrefter |
| 5.2 | `framing_variety` (`F1`–`F3`) | Presets for tett og videre utsnitt per kamera | Utsnittet skifter bare når kameraet er av lufta |
| 5.3 | `slow_zoom` (`Z1`–`Z3`) | Zoomfarten fra KA5 | Zoomen er rolig nok på lufta, og aldri med pan eller tilt samtidig |
| 5.4 | `ai_tracking` (`AT1`–`AT6`) | KA7 godkjent (Q16) | Kameraet følger rolig; CutCut flytter det ikke selv mens tracking er på |
| 5.5 | `video_confirm` (`V1`, `V2`, `V5`, `PV3`) | 4.3 godkjent; videolaget med ansikt i gang | Færre kutt på lekkasje; ingen kutt til bilde uten ansikt eller i bevegelse |
| 5.6 | `reactions` (`R1`–`R3`, `V3`) | `video_confirm` på | Reaksjonsbilder i talerens pause, maks ett per pause, og ikke på korte svar |
| 5.7 | `seat_check` (P12) | Ansikt og munn i videolaget. Står i skygge fra start | Tre sendinger: alle riktig, én gjest ved feil kamera, to som har byttet plass. Logg → søk «Plassjekk»: riktig svar innen 2 min? Så **På**: det gule feltet på touch, og «Bytt i CutCut» gir riktig person i bildet |
| 5.8 | `audio_adapt` (P13) | Lekkasjen målt i steg 5. Står i skygge fra start | Flytt én mikrofon nærmere naboen etter at fasit er lagret. Oppsett → steg 5 → «Denne økten»: lekkasjen for den mikrofonen nærmer seg det nye. Etter perioden avgjør avspilling av opptakene (P11) om den skal på |

Til slutt: alle godkjente brytere på samtidig i én prøvesending, så alle av igjen. Med alle av skal kuttene være som i grunnmodus.

## 6. 72-timerstesten

Startes etter blokk 3, og får gå mens resten prøves. PC-en skal ikke startes på nytt i perioden.

```powershell
uv run cutcut hwtest soak --site C:\CutCut\site --hours 72
```

Testen kjører ved siden av tjenesten, uten innlogging, og endrer ingenting. Hvert 10. minutt måles minne og håndtak per CutCut-prosess, omstarter, tilkoblingene (ATEM, Companion, Pearl, kameraer, lyd) og helsen. Stegene står i [`maskintest.md`](maskintest.md#72-timerstesten-so-8).

Godkjent når minne og håndtak vokser under 5 % etter første time, ingen prosess har startet på nytt, og ingen tilkobling er tapt. Avbrytes testen med Ctrl+C, skrives rapporten med det som er målt. Rapport til SO-8.

## 7. Akseptanse (10.4)

Kriteriene for v1, og hvor i perioden de sjekkes. Det som kan måles fra loggen, regner `cutcut hwtest akseptanse` ut (A1–A5, `maskintest.md`); feilsøkingsmodus må være på for A1. Kort, e-post og Panopto er tatt ut av perioden (gjøres etter at studioet er tatt i bruk).

| Kriterium | Sjekkes i |
| --- | --- |
| Kutt innen 150 ms etter bekreftelsestiden | `hwtest akseptanse` A1, sendingene i 4.2 |
| Færre enn 2 kutt per 10 min som operatøren ville gjort annerledes | Klippelista (Q2) mot loggen fra 4.2 |
| Ingen kutt til kamera i bevegelse eller tomt bilde | Alle prøvesendingene, til sammen minst 10 timer med 72-timerstesten |
| Lekkasje: ingen kutt til andre i 10 min | 4.5 |
| Content innen 1 s | 4.6 |
| Modusene `N1`–`N4C` med riktig utvalg og reservebilder | Testsendingene i 4.2 (1, 2 og 3–4 personer, med og uten laptop) |
| Videolaget kan drepes; `core` tilbake innen 5 s | 4.4 |
| Pearl-status på touch stemmer; stopp uten trykk varsles innen 5 s | `hwtest pearl` P4 og P5 (2.5); steg 9 |
| 72 timer uten minnelekkasje eller tapte tilkoblinger | Blokk 6 |
| Minst 90 % av taler-kuttene på `K1` eller `K2` | `hwtest akseptanse` A2 |
| Preview viser neste bilde minst 300 ms før `TAKE` i 95 % av kuttene | `hwtest akseptanse` A3 |
| Ingen kutt tilbake innen 4 s (`H2`) | `hwtest akseptanse` A4, alle prøvesendingene |
| Alle brytere av gir samme resultat som grunnmodus | Slutten av blokk 5 |
| Opptak fra touch vises i teknikervinduet innen 1 s, og omvendt | Steg 9 |
| Kun lyd: lyd og «Kun lyd»-grafikk, ingen kamera beveger seg | En kort prøve med showtypen «Kun lyd» |

## Hvis noe går galt

Fullstendige runbooks ligger i [`docs/runbooks/`](../runbooks/README.md).

- **Ingen lyd:** Helse viser `H-AUD-1` med grunnen fra `audio-capture`. Vanligst: ASIO-driveren mangler, eller RØDECaster står ikke i multitrack-modus.
- **ATEM svarer ikke:** sjekk IP under Oppsett, og at `atem-bridge` kjører under Helse → Prosesser. Er ATEM-adressen endret, startes `atem-bridge` på nytt neste gang supervisor starter den.
- **Ingen kamerabilder:** `H-VID-1`. Sjekk at INOGENI (eller ATEM-ens USB-C) sitter i en USB 3-port, at riktig metode er valgt under Oppsett, steg 6, og at ingen andre programmer har enheten åpen.
- **Touch er svart:** kiosk-vakten starter Edge på nytt etter 30 s. Loggen ligger i `C:\Users\cutcut-kiosk\AppData\Local\CutCut\kiosk-vakt.log`.
- **En bryter går til skygge av seg selv:** den har feilet og varslet gult. Grunnen står under Regi og i varslene.
- **Feilsøkingspakke:** teknikervinduet → Logg → «Feilsøkingspakke». Den har ingen passord, og den legges ved issuet.
