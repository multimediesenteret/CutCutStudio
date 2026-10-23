# Plan: alt klart før studioperioden

Status: godkjent av eier 2026-10-22 (D-066) · Erstatter rekkefølgen i `features.md` for M4 · Spes. 5.6, 5.13, 6, 7, 8.4, 11 steg 10–11

**Leveransestatus 2026-10-22:** P1–P9 er bygget og slått sammen (issues #176–#184). Bryterne er ferdige først når de er prøvd i studio etter `docs/studio/testdag.md` blokk 5; P9 venter på gjennomlesing av eier.

## 1. Mål

Studioet kan bare bookes i én periode. Alt som kan lages og prøves uten studio, lages derfor før perioden. Da brukes perioden bare til tre ting:

1. **Maskintester:** ATEM, Companion, Pearl, RØDECaster, kameraer og capture-kortet (INOGENI).
2. **Kalibrering:** setup-hjelperens ti steg, rutekart, mikrofonfasit, presets, kamerafart og farge.
3. **Prøving:** grunnmodus først, så hver bryter alene i skyggemodus og deretter live.

Til perioden kommer en ferdig sjekkliste der hvert punkt sier hva som prøves, hvordan, og hva som er godkjent (`docs/studio/testdag.md`).

## 2. Det som er bestemt (2026-10-22)

| Hva | Beslutning |
| --- | --- |
| Regi-PC | i5-12500, 16 GB, RTX 4060 Ti, 250 GB SSD; vanlig Windows; Companion på samme PC (D-062). Multiviewen tas inn med INOGENI 4KXUSB3 som planlagt (D-068) |
| Live tekst og turbytte | Ut av v1, prosessen `stt` utgår (D-063) |
| Nett | Egen uadministrert switch for utstyret; PC-en har ett kort mot switchen og ett mot campusnettet for trafikk ut (D-064) |
| Drift | Eget servicevindu; UPS og strøm i sjekklistene; ingen teknikerlister nå; support-e-post i appen (D-065) |
| Senere, etter at studioet er tatt i bruk | E-postvarsling (Q40), kortleser og kort-API (SE-4, SE-5, Q4), Panopto (Q5) |

## 3. Arbeidspakker

Hver pakke er én PR (D-059). Rekkefølgen er valgt slik at det som trengs i studio først, kommer først, og at bryterne bygger på skyggemodus.

| # | Pakke | Innhold | Prøves før studio med | I studio |
| --- | --- | --- | --- | --- |
| P1 | Studio-PC, nett og support | Capture-kortet (INOGENI) funnet på navnet i videolaget, og videolaget startet av supervisoren. Setup-steg 1 og 2 for to nettverkskort, og en helsesjekk for studio-kortet (`H-NET-1`). Support-e-post under Innstillinger, vist på touch ved «Hjelp» og i varsler. Live tekst og turbytte fjernes (D-063). Tekst om INOGENI erstattes | Videofil og syntetisk kilde; falske nettverkskort | Kortet leser multiviewen i 1080p50; begge nettverkskortene |
| P2 | Skyggemodus per bryter (F-1) | Hver bryter har `av`, `skygge` og `på`. I skygge kjører reglene og logges med `shadow: true`, uten å påvirke kuttene. Forutsetninger sjekkes (GPU, makrosjekk grønn, kamera støtter fart), og teknikervinduet viser hvorfor en bryter er sperret. En bryter som feiler, går selv til skygge og varsler gult | Regeltester og simulator | Hver bryter prøves alene i skygge før den slås på |
| P3 | Layouter (F-6, `L1`–`L4`) | Reglene for bilde-i-bilde og firedelt, med makroene 10–40 (7.2). Regnes på lufta først når ATEM bekrefter; `LAYOUT_RESET` ved tvil | Regeltester; simulatorscenario med fire personer og laptop | Makroene lages i ATEM (steg 8); prøves i skygge, så live |
| P4 | Vekslende utsnitt og langsom zoom (F-3 `F1`–`F3`, F-5 `Z1`–`Z3`) | Utsnitt tett/videre når kameraet er av lufta; zoom inn sakte på samme taler; aldri på kandidat, aldri med pan og tilt samtidig | Falske kameraer (VISCA/OSC) og simulator | Laveste zoomfart måles per kamera |
| P5 | AI-tracking (F-7, `AT1`–`AT6`) | Tracking av/på per OBSBOT, med låst fart og zoom, og sperre for egne bevegelser mens tracking er på | Falsk OSC | `SetAiEnable` prøves på kameraet (Q16) |
| P6 | Tung del av videolaget (VI-6) | Ansikt, munnbevegelse, smil og nikk per rute på GPU (ONNX Runtime med CUDA, DirectML som reserve). Modeller med åpen lisens, lastet ned med `tools/fetch_models.py` | Videofiler med kjente svar; måling av tid per bilde på RTX 4060 Ti-klassen (CPU i CI) | Ytelse og treffsikkerhet på studiobildet |
| P7 | Videobekreftelse og reaksjoner (F-2 `V1`, `V2`, `V5`, `PV3`; F-4 `R1`–`R3`, `V3`) | Munnbevegelse korter ned `T2` og avslører lekkasje; preview må vise gyldig ansikt før `TAKE`; reaksjonsbilder i talerens pause | Regeltester og simulator med syntetiske målinger fra P6 | Skygge mot grunnmodus, så live |
| P8 | Fargematching (F-10) | Gråkort i bildet: hvitbalanse og eksponering justeres i 3–5 runder mot referansekameraet, bare når kameraet er av lufta | Syntetiske bilder og falske kameraer | Gråkort-test i studio |
| P9 | Sjekkliste for studioperioden | `docs/studio/testdag.md` skrives om til én plan for hele perioden: oppsett (UPS, strøm, switch, nettverkskort, Windows, Companion), maskintester, setup-hjelperens ti steg, grunnmodus, bryterne én og én, 72-timerstesten og akseptansen (10.4). Med det som manglet for å følge den: `cutcut hwtest soak` for 72-timerstesten, og skyggefilter og bryter-kolonne i loggen | Gjennomlesing; testene for 72-timersmålingen | Følges punkt for punkt |

Web-simulatoren med motoren i nettleseren (PL-03 trinn 2) og avspilling av ekte forløp (SIM-8) venter: den første trengs ikke i studio, og den andre trenger opptak derfra (Q1). Opptakene til Q1 og Q2 tas i studioperioden.

## 4. Krav som gjelder alle pakkene

- Grunnmodus gir samme kutt med alle brytere av som før pakken (10.4). Simulator-forløpene lages på nytt og sammenlignes.
- Ingen bryter kan flytte et kamera som er på program eller preview (I2), og ingen bryter stopper et opptak (I7).
- En bryter som mangler forutsetning kan ikke slås på; teknikervinduet sier hvorfor.
- Alt som trenger GPU, har en CPU-vei som er treg men riktig, så testene går i CI.

## 5. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| P1 | Studio-PC, nett og support | Capture-kortet finnes på navnet; `H-NET-1`; support-e-post; D-063 gjennomført |
| P2 | Skyggemodus per bryter | Tester grønne; teknikervinduet viser sperre og skygge |
| P3 | Layouter | `L1`–`L4` testet; scenario i simulatoren |
| P4 | Utsnitt og zoom | `F1`–`F3`, `Z1`–`Z3` testet mot falske kameraer |
| P5 | AI-tracking | `AT1`–`AT6` testet mot falsk OSC |
| P6 | Tung del av videolaget | Treffsikkerhet målt på videofiler; tid per bilde målt |
| P7 | Videobekreftelse og reaksjoner | `V1`–`V5`, `PV3`, `R1`–`R3` testet |
| P8 | Fargematching | Konvergerer på syntetiske bilder |
| P9 | Sjekkliste | Gjennomgått av eier |

Hver bryter er først ferdig når den er prøvd i studio (rapport i issuet), som før (M4-kriteriet i `features.md`).

## 6. Senere utvidelser

Ting som er vurdert, men ikke skal bygges før studioet er i drift:

| Hva | Hvorfor senere |
| --- | --- |
| DeckLink-kort som capture (Blackmagic DeckLink Mini Recorder HD) | Regi-PC-en får kortet, men ikke alle studioer har det. INOGENI er enklere og er standard (D-068). CutCut finner allerede capture-kortet på navnet, så en DeckLink-kilde er mest oppsett og maskintest |
| Teksting etter opptak | Live tekst er tatt ut (D-063). Etter opptaket betyr forsinkelsen ingenting |
| Blikkretning (`V6`) | Eksperimentell i spesifikasjonen |
| Tyngre taler-modell på GPU (ASD) | Bare hvis studioopptakene viser at ansikt og munn på CPU ikke er godt nok (D-067) |
| Web-simulatoren med motoren i nettleseren (PL-03 trinn 2) | Trengs ikke i studio |
| Statuslys i rommet (Kuando Busylight UC Omega): rødt under opptak, grønt når klart, blått ved feil, valgfritt per tilstand i appen | Forslaget er klart (`docs/research/statuslys-busylight.md`), men en test med én lampe må avgjøre metoden først (Q42) |
