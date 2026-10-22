# RØDECaster Pro II – standardoppsett

Dato: 2026-10-21 · Status: **standard** (beslutning D-032). Avvik krever ny rad i beslutningsloggen.

Dette er oppsettet CutCut Studio forventer. Setup-hjelperen (spesifikasjonen 8.4, steg 5) kontrollerer hvert punkt og lagrer resultatet i `baseline.yaml`.

## Firmware og driver

| Hva | Standard | Hvorfor |
| --- | --- | --- |
| RØDECaster-firmware | **1.7.6** (stabil, 23.09.2026) | Siste stabile utgave. Kanalkartet etter fader kom i 1.7.3 (11.03.2026); 1.7.4–1.7.6 er feilrettinger og RODECaster Sync, ingenting som påvirker multitrack |
| Beta-firmware | **Aldri** (1.7.7 er beta per 21.10.2026) | Stabilitet over nye funksjoner |
| Automatisk oppdatering | Av. Oppdateres bare i servicevindu etter test i skyggemodus | Kanalkart og driver kan endre seg |
| PC-driver | Siste **RØDECaster ASIO-driver** kompatibel med 1.7.3+ (ny driver kom med 1.7.3) | Se `docs/research/lyd-fra-rodecaster.md` |
| Virtual Devices-driver | **Ikke** installert | Kan ikke kjøre samtidig med ASIO |
| Versjoner noteres | `site/<studio>/equipment/versions.yaml` | Skrives av `installer/setup-pc.ps1 -VersionsYaml …`. Sammenligning i morgensjekken er ikke bygget |

## Plassering og faderkart

Programlederen sitter ved RØDECaster og betjener den. Programlederen har derfor alltid fader 1, mic 1 og samme farge, uansett show.

| Fader | Kilde | Inngang | Deltaker | Farge | Multitrack-kanal (USB 1) | CutCut-ID |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Mic | Combo 1 | **Programleder** | Magenta | 3–4 | `M1` / `P1` |
| 2 | Mic | Combo 2 | Gjest 1 | Cyan | 5–6 | `M2` / `P2` |
| 3 | Mic | Combo 3 | Gjest 2 | Lilla | 7–8 | `M3` / `P3` |
| 4 | Mic | Combo 4 | Gjest 3 | Oransje | 9–10 | `M4` / `P4` |
| 5 | Laptop-lyd | USB 2 | – | Hvit | 11–12 | `M5` (regel `CT5`) |
| 6 | SMART Pads (jingler) | intern | – | RØDE-standard | 13–14 | ignoreres |
| 7–9 | Ikke i bruk (virtuelle) | – | – | – | 15–20 | ignoreres |

Hovedmiks ligger alltid på kanal 1–2.

**Regel:** mic N ligger på fader N, og kanalen er `2 × N + 1` (venstre i stereoparet; mono-mikrofoner kommer som dobbel mono). Med færre enn fire deltakere står de ubrukte mic-faderne der fortsatt, men dempet og ubrukt. Rekkefølgen flyttes aldri, slik at kanalkartet er det samme for alle show.

**Bordplan:** programleder ved mikseren. Gjestene plasseres i fast rekkefølge med klokka fra programlederen (gjest 1 nærmest). Kamerakartet følger personene: `CAM 1` = programleder, `CAM 2–4` = gjest 1–3, slik prototypen viser. Multiview-rutene må stemme med dette (spesifikasjonen 2.1).

## Innstillinger på RØDECaster

| Meny | Innstilling | Verdi |
| --- | --- | --- |
| Outputs → Multitrack → USB 1 Output | Multitrack | **På, Pre-Fader** (rene spor, uten fader og prosessering) |
| Outputs → USB 1 Input | Modus | Standard (ikke «Expanded», det er for Virtual Devices) |
| Lyd | Samplingsfrekvens | 48 kHz |
| Mic-kanal 1–4 | Type | Mono, panorert midt |
| Mic-kanal 1–4 | Gain | Satt med setup-hjelperen: snakk normalt, topp rundt −18 dBFS |
| Mic-kanal 1–4 | Prosessering (APHEX, høypass, kompressor) | På etter smak; påvirker bare hovedmiksen, ikke sporene CutCut leser |
| Mic-kanal 1–4 | Kanalfarge | Se fargetabellen; nærmeste farge i RØDE-paletten |
| Mic-kanal 1–4 | Kanalnavn (hvis firmware tillater) | `PROG`, `GJEST 1`, `GJEST 2`, `GJEST 3` |
| Automatiske funksjoner | Auto-mute, ducking og lignende | Av. CutCut skal se de samme signalene som deltakerne lager |
| Hovedmiks ut | Til ATEM | Analog lydinngang på ATEM (spesifikasjonen 2.3 var skrevet for Mini Extreme; på HD8 ISO bekreftes inngangen i studio) |

## Når programlederen demper en mic

Programlederen betjener mikseren og kan dempe en gjest eller dra ned en fader. Med pre-fader multitrack hører CutCut trolig fortsatt den dempede mic-en, og kunne klippet til noen som ikke høres i sendingen.

Tiltak (regel `S6`, bygget i AU-4):

- CutCut sammenligner hver mic med hovedmiksen (kanal 1–2). Er mic-en aktiv, men bidraget i hovedmiksen mangler (lav korrelasjon over 0,5 s), regnes den som **dempet**: ingen kutt til den personen, og mic-stripen viser «dempet på mikser».
- Maskintesten for lyd skal bekrefte om pre-fader-sporet faktisk inneholder lyd fra en dempet kanal, og om post-fader er et bedre valg (Q24).

## Fargene utenfor mikseren

Samme farge følger deltakeren gjennom hele kjeden, så alle vet hvem som er hvem uten å lese:

- **Mikrofon:** fargeflagg eller fargering på mikrofonarmen i deltakerens farge.
- **Touch-skjermen:** når brukeren registrerer gjester, får hver gjest en plass med farge og tall («Gjest 1 · cyan mikrofon»).
- **Teknikervindu og simulator:** mic-stripe, setebrikke, ansiktsboks i multiview, tidslinje. Se `docs/design/farger.md`.
