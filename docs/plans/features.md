# Plan: brytere og steg 11 – farge og Panopto

Status: godkjent (D-046). Rekkefølgen før studio står i `for-studio.md` (D-066); live tekst og turbytte er tatt ut (D-063) · Milepæl: M4 · Spes. 5.6, 5.13, 6.4, 6.5, 7.6, 11 steg 10–11; D-006, D-009, D-011, D-023; ADR-0011 · Moduler: `core/rules/`, `vision/`, `stt/`, `devices/cameras/`, `session/`

## 1. Formål og avgrensning

Alt utover grunnmodus. Hver bryter bygges, testes i simulator, og **testes alene i studio** før den kan slås på i drift (M4-kriteriet). Mens studioet ikke er i bruk testes den live; når studioet er i drift, i skyggemodus (D-049). Grunnmodus skal gi samme resultat med bryterne av som med bryterne på og videolaget borte (10.4).

**Rekkefølge (spes. 11 steg 10):**

| # | Bryter | Regler | Krever | Ny prosess/del |
| --- | --- | --- | --- | --- |
| 1 | `video_confirm` | `V1`, `V2`, `V5`, `PV3` | Tung del av videolaget, GPU | `vision` (tung) |
| 2 | `framing_variety` | `F1`–`F3`, `V4` | PTZ-drivere, videolag | – |
| 3 | `reactions` | `R1`–`R3`, `V3` | Videolag | – |
| 4 | `slow_zoom` | `Z1`–`Z3` | Laveste zoomfart målt per kamera | – |
| 5 | `layouts` | `L1`–`L4` | ATEM-makroer 10–40, `H-ATEM-3` grønn | – |
| 6 | ~~`live_transcript`~~ | – | Tatt ut av v1 (D-063) | – |
| 7 | ~~`turn_prediction`~~ | – | Tatt ut av v1 (D-063) | – |
| – | `ai_tracking` | `AT1`–`AT6` | OBSBOT med `SetAiEnable` (Q16) | – |

`bird` og `content` er på som standard og bygges i grunnmodus (`core.md`, `vision.md`).

**Steg 11:** fargematching med gråkort (6.4), bare off air, 3–5 runder mot referansekamera; Panopto-publisering når Q5 er avklart.

## 2. Grensesnitt

- Brytere er felt i `Features` (show-oppsett) og kan endres i sanntid (`POST /features`, ADR-0011). En bryter som mangler forutsetning (for eksempel GPU eller grønn makrosjekk) kan ikke slås på; teknikervinduet viser hvorfor.
- Hver bryter kan settes til `shadow` i tillegg til av/på: reglene kjører og logges med `shadow: true`, men påvirker ikke kuttene. Slik testes hver bryter alene (M4).
- `stt` får `audio.pcm` fra `audio-capture`, sender `stt.text` (per mic, med tid) og stopper selv når GPU trengs til videolaget (5.13). Live tekst lagres ikke som standard (12.4, Q10).

## 3. Tilstander og feil

- En bryter som feiler (unntak, manglende data) slår seg selv over i `shadow`, logger og varsler gult. Grunnmodus berøres aldri.
- Layouter: regnes på lufta først når ATEM bekrefter (5.6); `LAYOUT_RESET` hvis noe er uklart.
- Farge: aldri på kamera på PGM/PVW; avbrytes hvis kameraet blir kandidat.

## 4. Avhengigheter

NB-Whisper (Apache 2.0) via whisper.cpp eller ONNX; VAP-modell (lisens sjekkes før bruk); ONNX Runtime GPU. Utstyr: GPU (Q20), ATEM-makroer laget i studio, gråkort.

## 5. Testplan

- Regeltester per ID som i `core.md`.
- Simulator-scenarioer per bryter.
- Studiotest per bryter (skyggemodus når studioet er i drift): sammenligning med menneskelig klippeliste (Q2) eller med grunnmodus; rapport i issue før bryteren kan slås på.
- `live_transcript`: forsinkelse og at `core` ikke påvirkes når `stt` dør.

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| F-1 | `shadow`-tilstand per bryter og forutsetningssjekk | Teknikervinduet viser hvorfor en bryter er sperret. Gjort (P2) |
| F-2 | `video_confirm` | Testrapport godkjent |
| F-3 | `framing_variety` | Testrapport godkjent |
| F-4 | `reactions` | Testrapport godkjent |
| F-5 | `slow_zoom` | Testrapport godkjent per kamera |
| F-6 | `layouts` | Testrapport godkjent. Reglene er bygget og testet mot simulator (P3); prøves i studio |
| F-7 | `ai_tracking` | Testrapport godkjent |
| F-8 | ~~`live_transcript`~~ | Tatt ut av v1 (D-063) |
| F-9 | ~~`turn_prediction`~~ | Tatt ut av v1 (D-063) |
| F-10 | Fargematching | Gråkort-test i studio |
| F-11 | Panopto | Når Q5 er avklart |

## 7. Åpne spørsmål

- Q5 (Panopto), Q6 (Canon), Q16 (AI-tracking), Q19 (blandede kameraer), Q20 (GPU), Q10 (live tekst og personvern).
