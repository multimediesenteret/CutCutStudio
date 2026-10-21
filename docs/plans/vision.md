# Plan: `vision` – videolaget

Status: godkjent (D-046) · Milepæl: M3 (lett) og M4 (tungt) · Spes. 2.1, 2.6, 5.4, 5.5, 6 (alle), 8.4 steg 6, 8.5 (`H-VID-*`); D-003, D-021; ADR-0003 · Mappe: `src/cutcut/vision/`

## 1. Formål og avgrensning

Leser ATEM-multiviewen via INOGENI 4KXUSB3, deler bildet i ruter etter rutekartet og sender målinger per rute til `core` 5–15 ganger i sekundet. Tar aldri beslutninger selv (6).

**Delt i to (PL-06), så grunnmodus aldri avhenger av GPU:**

| Del | Innhold | Kjører på | Milepæl |
| --- | --- | --- | --- |
| **Lett** | Capture, rutekart, content-deteksjon (6.2: `NO_SIGNAL`, `STATIC`, `NEW_SLIDE`, `VIDEO`), bevegelse per rute (`V5`/`S1` med enkel bildedifferanse), PGM-bekreftelse, personer i fugleperspektiv (enkel) | CPU, OpenCV | M3 |
| **Tung** | Ansikt (SCRFD/YuNet), munn, smil og hoderetning (MediaPipe Face Landmarker), aktiv taler (Light-ASD), utsnittsfeil (`V2`, `V4`) | GPU, ONNX Runtime CUDA/TensorRT, DirectML som reserve | M4 (brytere `video_confirm`, `reactions`, `framing_variety`) |

`B`- og `CT`-reglene i `core` trenger bare den lette delen.

## 2. Grensesnitt

- Inn: UVC-capture (DirectShow/Media Foundation via OpenCV eller FFmpeg), YUY2 1080p50. Rammer tas med 15 Hz; resten forkastes tidlig for å spare CPU.
- Rutekart: `site/<studio>/equipment/multiview_map.yaml` med koordinater 0–1 og 4 % innkutt (6.1).
- Ut: `vision.tile` (6.6), `vision.content` (6.2), `vision.pgm` (hva som faktisk er på lufta), `vision.status` (fps, forsinkelse, siste feil).
- Bildeutsnitt til teknikervinduet: små JPEG-er av multiview maks 2 per sekund på eget emne, bare når teknikervinduet er åpent.

## 3. Tilstander og feil

| Situasjon | Gjør |
| --- | --- |
| Ingen rammer i 1 s | `vision.status` rød; `core` går til «Bare lyd» (6.6) |
| Feil format (ikke 1080p50) eller rutene gjenkjennes ikke | `H-VID-1`/`H-VID-2` gul; bare lyd |
| GPU-feil i tung del | Tung del slås av; lett del fortsetter; bryterne som trenger den sperres |
| Prosessen henger | Supervisor restarter; kutting fortsetter på lyd (10.4) |
| Antall personer i fugleperspektiv avviker i over 10 s | Advarsel på skjermene; oppsettet endres aldri (6.3) |

Prosessen kjører med lavere prioritet enn `core` og `audio-capture`.

## 4. Avhengigheter

Lett: `opencv-python-headless`, `numpy`. Tung: `onnxruntime-gpu` (CUDA/TensorRT) eller `onnxruntime-directml`, `mediapipe`, modellene i `models/manifest.yaml` med lisens og SHA-256. Utstyr: INOGENI 4KXUSB3 på egen USB 3-port, NVIDIA RTX (Q20).

## 5. Testplan

- Content-deteksjon på opptatte og syntetiske klipp: ny slide innen 1 s, laptop frakoblet innen 1 s (10.4).
- Rutekart: bilde av multiview med kjente kilder gir riktig rute → kilde.
- Ytelse lett del: under 25 % av én kjerne ved 15 Hz.
- Drapstest: drep `vision` under scenario → kuttingen fortsetter (10.4).
- **Maskintest** `tools/hw-test/inogeni.py`: format, fps, forsinkelse ATEM → PC med blinkende testbilde, 60 min uten tapte rammer.

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| VI-1 | Capture-adapter med falsk kilde (videofil) og rutekart | Ruter publiseres fra fil |
| VI-2 | Content-deteksjon 6.2 | Kriteriene i 10.4 for content grønne |
| VI-3 | Bevegelse per rute og PGM-bekreftelse | `S1` får ekte data |
| VI-4 | Maskintest INOGENI | Rapport i issue |
| VI-5 | Rutekart-forslag i setup steg 6 | Hjørner kan dras i GUI |
| VI-6 | Tung del: ansikt, munn, smil, ASD (M4) | `video_confirm` testet alene i studio |

## 7. Åpne spørsmål

- Q13: hvilket kamera er fugleperspektiv?
- Q14: står laptopen alltid på inngang 6?
- Q20: hvilken GPU har regi-PC-en?
- Q1: multiview-video fra ekte sendinger.
