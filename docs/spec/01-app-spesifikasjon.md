&#91;embedded content: CutCut Studio · logo: tale inn, klipp, kamera på lufta\]

# CutCut Studio – app-spesifikasjon v1

Oct 20, 2026 · @Magnus Lian

CutCut Studio er en Windows-applikasjon som klipper en live videopodcast automatisk. Den lytter på hver mikrofon fra RØDECaster, ser alle kameraene via ATEM-multiviewen, og kaller ferdige oppsett i ATEM gjennom Companion. Den styrer PTZ-kameraene over IP, og leser status fra Epiphan Pearl Nexus som tar opp sendingen.

Dokumentet er skrevet for to lesere. Mennesker leser første setning i hver seksjon og tegningene. En AI-utvikler bygger fra tabellene, ID-ene, konfigurasjonsformatet og akseptansekriteriene, som er ment å kunne brukes direkte. Fanen «Evaluering og bakgrunn» forklarer valgene. Ved uenighet mellom dokumentene gjelder rekkefølgen i `docs/forprosjekt/overlevering.md` (beslutningsloggen først).

**Omfang v1:** 1–4 deltakere med hver sin mic, ett fugleperspektiv-kamera over bordet, én laptop på HDMI, live-produksjon uten etterarbeid, OBSBOT Tail 2 og Canon CR-N300. PiP og quad er støttet, men avslått som standard. Brukeren logger inn med adgangskortet, velger hvem som er med og video og lyd eller bare lyd på én touch-skjerm, og trykker Start (D-036). Opptak kan startes både fra touch-skjermen og teknikervinduet.

**Ikke i v1:** NDI, etterarbeid, Panasonic- og Sony-drivere (fase 2), grafikk og navneskilt, styring av lydmiksen, publisering til Panopto (forberedt i GUI og datamodell, bygges senere).

### Ordliste og faste ID-er

| ID | Betyr | Merknad |
| --- | --- | --- |
| `P1`–`P4` | Deltaker | `P1` er vert som standard |
| `M1`–`M4` | Mikrofon = RØDECaster fader 1–4 | Én mic per deltaker, `Mx` hører til `Px` |
| `M5` | Laptop-lyd = RØDECaster fader 5 (USB 2) | Brukes av content-reglene (`CT3`, `CT5`) |
| `C1`–`C4` | Nærbilde-kamera for `P1`–`P4` | ATEM-inngang 1–4. Vises i GUI som «CAM 1»–«CAM 4» |
| `C5` | Fugleperspektiv over bordet (`BIRD`) | ATEM-inngang 5, fast kamera. Vises som «CAM 5» |
| `C7` | Valgfritt halvtotal-kamera | ATEM-inngang 7, brukes ved 1–2 deltakere |
| `LAPTOP` | Content fra laptop på HDMI | ATEM-inngang 6. Vises som «IN 6» |
| Bilde (shot) | Det som går på program | `CU:P2`, `BIRD`, `WIDE`, `CONTENT`, `PIP:P2+CONTENT`, `PIP:P1+P2`, `QUAD4`, `QUAD3C` |
| Modus | Regelsett valgt ut fra antall deltakere og om content er aktivt | `N1`–`N4` etter antall deltakere, `N1C`–`N4C` når content er aktivt, `A` for kun lyd |
| Regel-ID | Hver regel har fast ID som vises i loggen | `T` tale, `V` video, `B` fugleperspektiv, `CT` content, `L` layout, `S` sikkerhet, `PV` preview, `K` kuttpunkt, `H` hold, `R` reaksjon, `F` utsnitt, `Z` zoom, `AT` AI-tracking. `CT` og `PV` het tidligere `C` og `P`; de ble endret for ikke å kollidere med kamera- og deltaker-ID-ene (D-041) |
| Motor | Tjenesten som tar beslutninger | Kjører på regi-PC-en |

## 0. Agent-brief

Dette dokumentet er spesifikasjonen et AI-agentteam starter prosjektet fra. Første leveranse er ikke kode, men én implementasjonsplan per modul etter malen i 0.4, godkjent av et menneske før bygging starter.

### 0.1 Oppdrag

- Bygg CutCut Studio slik seksjon 1–11 beskriver. Der dokumentet sier «forslag» eller «anslag», skal agenten måle og foreslå, ikke gjette.
- Prioritet: stabilitet før enkelhet, enkelhet før funksjoner. Grunnmodus bygges først; bryterne i 5.13 etterpå.
- Systemet skal stå i måneder uten tekniker. Hver beslutning vurderes mot det.

Protokoller, kommandoer, API-er og lenker til all leverandørdokumentasjon står i fanen Teknisk referanse. Agenten bruker den som oppslagsverk og legger nye funn inn der.

### 0.2 Ufravikelige regler

1. **I1:** Sendingen avhenger aldri av at CutCut kjører. ATEM og Pearl fortsetter alene hvis PC-en stopper.
2. **I2:** Kamera på program eller preview flyttes aldri (eneste unntak: langsom zoom `Z` når den er slått på).
3. **I3:** Regelmotoren er deterministisk: samme inndata gir samme beslutning, og den lærer ikke i sanntid. Modeller brukes til å måle (tale, ansikter, content), ikke til å bestemme.
4. **I4:** Hver beslutning har regel-ID og målte verdier i loggen.
5. **I5:** Mennesket vinner alltid. Manuelle valg på ATEM, Stream Deck eller skjermene overstyres aldri; motoren tilpasser seg det den leser tilbake.
6. **I6:** Ingen skytjeneste i sanntidssløyfen. Kort-API og Panopto brukes bare ved innlogging og etter opptak.
7. **I7:** Opptak stoppes aldri automatisk, bare av en person.
8. **I8:** Kortnummeret (UID) lagres og logges aldri; bare brukernavnet.

### 0.3 Arkitekturbeslutninger

| ID | Beslutning | Hvorfor |
| --- | --- | --- |
| `ADR-01` | Én Windows 11-PC kjører alt: motor, Companion, touch-skjerm og teknikervindu | Én maskin å drifte; brukeren har én skjerm å forholde seg til |
| `ADR-02` | Python 3.12 med strenge typer (mypy strict, Pydantic v2); avhengigheter låst med `uv`; egen Python i app-mappen | Lyd- og modelløkosystemet; samme installasjon hver gang, uavhengig av system-Python |
| `ADR-03` | Tre prosesser (core, vision, stt) under en supervisor som kjører som Windows-tjeneste (WinSW) | Feil i bildeanalyse eller tekst stopper aldri klippingen |
| `ADR-04` | Avstemmingssløyfe: hvert sekund sammenlignes ønsket og faktisk tilstand for ATEM, Pearl og kameraer; avvik logges og motoren tilpasser seg | Tåler tapte kommandoer og manuelle inngrep uten å «slåss» mot operatøren |
| `ADR-05` | Alle enhetskommandoer er idempotente, har tidsavbrudd, går gjennom kø per enhet og har kretsbryter som pauser en enhet som feiler gjentatte ganger | Én treg enhet kan ikke henge resten |
| `ADR-06` | Oppsett som YAML i git med skjema; kjøredata i SQLite (WAL); logg som JSON-linjer | Lett å lese, versjonere og gjenopprette |
| `ADR-07` | Grensesnitt i React + TypeScript, servert lokalt; touch-skjermen i Edge kiosk-modus med tilordnet tilgang | Brukeren kan ikke gå ut av appen; samme kode for begge skjermer |
| `ADR-08` | Kortleser (ELATEC TWN3) i virtuell COM-port-modus, ikke som tastatur | Virker uten tastaturfokus og gir pålitelig kortnummer |
| `ADR-09` | Kutt og layouter går via Companion; ATEM leses direkte | Stream Deck og motor bruker de samme knappene |
| `ADR-10` | Monoton klokke i motoren, NTP for veggklokke | Tidsregler påvirkes ikke av at klokka justeres |
| `ADR-11` | Brytere kan endres i sanntid fra teknikervinduet | Nye funksjoner kan prøves uten ny versjon |

### 0.4 Mal for implementasjonsplan

Agenten lager én fil per modul i `docs/plans/<modul>.md`, i rekkefølgen fra seksjon 11:

1. **Formål og avgrensning:** hvilke seksjoner og regel-ID-er modulen dekker.
2. **Grensesnitt:** inndata, utdata, meldinger og API, som Pydantic-modeller.
3. **Tilstander og feil:** hva som skjer ved tidsavbrudd, frakobling og ugyldige data.
4. **Avhengigheter:** biblioteker med låste versjoner, og utstyr den trenger.
5. **Testplan:** enhetstester per regel, falske enheter, simulator og akseptansekriteriene i 10.4.
6. **Leveranser:** små steg på under én dags arbeid, hvert med «ferdig når».
7. **Åpne spørsmål** til mennesker.

### 0.5 Konvensjoner

- Norsk i grensesnittet, engelsk i kode og kommentarer.
- Regel-ID-er og enhets-ID-er fra ordlisten brukes uendret i kode, logg og grensesnitt.
- Ingen blokkerende kall i asyncio-løkken; all I/O har tidsavbrudd.
- Hver modul kan kjøres mot simulatoren uten utstyr.
- Ingen hemmeligheter i git; de ligger i Windows Credential Manager.

## 1. Systemoversikt

Alle kameraer og laptopen går på HDMI eller SDI inn i ATEM. ATEM sender program til Pearl Nexus for opptak og multiview til regi-PC-en. PC-en får i tillegg hver mic fra RØDECaster over USB, og styrer resten over IP.

&#91;embedded content: systemtegning · signalflyt og styring\]

PC-en er det eneste nye utstyret, i tillegg til et USB-capture-kort og en touch-skjerm. Stopper PC-en, står ATEM på siste bilde og Pearl fortsetter opptaket, slik at sendingen aldri faller ut.

## 2. Utstyr og innstillinger

Alt utstyr settes opp én gang etter tabellene under, og innstillingene lagres som eksportfiler i studio-repoets `site/<studio>/equipment/`-mappe. Hele studioet kjører 1080p50, fordi norsk lysnett er 50 Hz og ulike bildefrekvenser gir flimmer og hakking.

### 2.1 Inngangskart og multiview

Multiview-oppsettet er en fast avtale mellom ATEM og videolaget: rutene må ligge der tegningen viser, ellers leser systemet feil kamera. CutCut sjekker avtalen ved oppstart og på forespørsel mot rutekartet, show-oppsettet og ATEM, og varsler med `H-MV-*`; anbefalt oppsett og sjekkene står i `docs/studio/multiview.md` (D-055).

&#91;embedded content: ATEM multiview · rutekart som videolaget leser\]

### 2.2 ATEM Mini Extreme ISO

> **Merknad D-053 (2026-10-21):** studioet har en **ATEM Television Studio HD8 ISO**, ikke Mini Extreme ISO. Innstillingene under gjelder fortsatt (1080p50, program til Pearl, multiview 2 + 8 til INOGENI over HDMI, makroer, eksport), men inngangene er SDI, «HDMI ut» leses som SDI-/HDMI-utgang, og modelltabellen lenger ned er ikke aktuell. Observert oppsett og avvik: `docs/studio/multiview.md`. Inngangskartet i studioet (D-054): inngang 1–4 = `C1`–`C4`, 6 = fugleperspektiv (`C5`), 7 = `LAPTOP`; ligger i `site/multimediesenteret/`.

| Innstilling | Verdi | Hvorfor |
| --- | --- | --- |
| Videoformat | 1080p50 | Samme som alle kameraer |
| Inngang 1–8 | Som rutekartet, korte navn: `C1`–`C4`, `BIRD`, `LAPTOP`, `C7` | Navnene vises i multiview og loggen |
| HDMI ut 1 | Program | Til Pearl Nexus for opptak |
| HDMI ut 2 | Multiview, layout med 2 store og 8 små ruter | Til USB-capture i regi-PC-en |
| Multiview-rute 8 | SuperSource | Videolaget ser hvilket PiP- eller quad-oppsett som er klart |
| Multiview-overlegg | Lydmålere av, safe area av, tally-rammer på | Mindre støy i bildeanalysen; tally viser hva som er på lufta |
| Overgang | Cut som standard; mix 12 bilder for layout-bytter | Layout-makroene setter selv overgangen |
| Lyd | Kun RØDECaster-miksen på lufta; kameraenes HDMI-lyd av | Unngår dobbel lyd og ekko. Lydforsinkelse justeres hvis bildet henger etter |
| Laptop-lyd | Via RØDECaster (egen kanal), ikke via ATEM | Alt lyd går gjennom én miks |
| Makroer | Se seksjon 7.2 | Layoutene bygges her og kalles fra Companion |
| ISO-opptak på USB-disk | Startes og stoppes fra teknikervinduet (7.7); av som standard | Pearl er hovedopptaker |
| Nettverk | Fast IP (se IP-plan) | Companion og motoren kobler til |
| Eksport | ATEM-oppsett eksporteres som `.xml` etter hver endring | Kan gjenopprettes på minutter |

Mediaspiller 1 i ATEM har en fast grafikk for «Kun lyd» (CutCut Studio-logo og «Lydopptak pågår»). Companion side 11 har en knapp som legger den på program, og motoren bruker samme knapp i modus `A`.

**Modellvalg:** spesifikasjonen fungerer med begge ISO-modellene, og CutCut finner modellen selv ved tilkobling.

|  | ATEM Mini Extreme ISO | ATEM Mini Extreme ISO G2 |
| --- | --- | --- |
| HDMI-innganger | 8 | 8 |
| HDMI-utganger | 2 | 3, og multiview kan legges på hvilken som helst |
| ISO-opptak | Alle innganger + program til USB-disk, med DaVinci Resolve-prosjekt | Alle 8 innganger (H.264 opptil 70 Mb/s) + program, lyd som WAV, DaVinci Resolve-prosjekt; til CFexpress eller USB-C |
| Nett | 1G | 1G + 10G for opptak og nettverkslagring |
| Utgangsbruk i CutCut | Ut 1 program → Pearl; ut 2 multiview → capture-kortet (DeckLink, D-062) | Ut 1 program → Pearl; ut 2 multiview → capture-kortet (DeckLink, D-062); ut 3 multiview eller program til skjerm i studio |
| Støtte i `atem-connection` og Companion | Godt etablert | Må verifiseres før produksjon, fordi modellen er ny |

G2 er det beste valget ved nytt kjøp, fordi den tredje utgangen gir en egen skjerm i studio uten å låne multiview-signalet. Før innkjøp bør det sjekkes at `atem-connection` og Companion sin ATEM-modul støtter G2 med lesing av tilstand, makroer, SuperSource og opptak. Gjør de ikke det, er Extreme ISO det trygge valget. Tallene er fra [Blackmagic sine tekniske spesifikasjoner](https://www.blackmagicdesign.com/products/atemmini/techspecs/W-APS-44).

### 2.3 RØDECaster Pro II

| Innstilling | Verdi |
| --- | --- |
| Fader 1–4 | Mic `M1`–`M4`, samme rekkefølge som deltakerne |
| Fader 5 | Laptop-lyd via USB 2 (`M5`), brukes av regel `CT5` (D-032) |
| USB 1 multitrack | På, pre-fader (rene spor) |
| Driver på PC | RØDECaster ASIO-driver. Virtual Devices-driveren installeres ikke |
| Utgang til ATEM | Hovedmiks til ATEM sin 3,5 mm-inngang |
| Firmware | Siste versjon, låst før produksjon |

### 2.4 Kameraer

| Innstilling | OBSBOT Tail 2 | Canon CR-N300 |
| --- | --- | --- |
| Video ut | HDMI 1080p50 | HDMI og/eller 3G-SDI 1080p50 |
| IP-styring | VISCA over IP og OSC på; AI-tracking av som standard (styres av CutCut), auto-zoom av | XC-protokoll på, egen API-bruker; VISCA over IP som reserve |
| NDI | Av | Av |
| AI-tracking | Av under sending (kan slås på av motoren off air) | Auto-tracking av |
| Hvitbalanse | Manuell / kelvin, startverdi 5600 K eller studiolyset | Manuell / kelvin |
| Eksponering | Manuell iris, gain og lukker 1/100 | Manuell iris, gain og lukker 1/100 |
| Presets | 1 = nær, 2 = halvnær, 3 = reserve | Samme |

Fugleperspektivet `C5` kan være hvilket som helst kamera med HDMI. Det står fast og trenger ingen IP-styring, men bør ha manuell hvitbalanse for fargematching.

### 2.5 Epiphan Pearl Nexus

| Innstilling | Verdi |
| --- | --- |
| Firmware | 4.24.1 eller nyere, som har [REST-API](https://www.epiphan.com/product-news/new-firmware-update-control-system-updates-rest-api-usb-button-led-light-support-and-easy-file-sharing/) |
| Inngang | HDMI fra ATEM ut 1 (program) |
| Opptaker | Én recorder for programmet, 1080p50, filnavn med dato og show-navn |
| API-bruker | Egen bruker med Basic-autentisering, kun for motoren og Companion |
| Tid | NTP mot samme tidskilde som regi-PC-en |

### 2.6 Regi-PC og nett

| Del | Krav |
| --- | --- |
| PC | Windows 11 Pro, 8+ kjerner, 32 GB RAM, NVIDIA RTX i mellomklassen, NVMe-disk (anslag; måles i uke 5) |
| Capture | **Endret (D-062):** Blackmagic DeckLink Mini Recorder HD i regi-PC-en (PCIe, SDI og HDMI inn, opptil 1080p60), lest som DirectShow-enhet med Blackmagic Desktop Video. Opprinnelig plan: INOGENI 4KXUSB3: HDMI inn, USB 3.0 ut som vanlig webkamera (UVC, uten driver), ukomprimert YUY2 i 1080p50, og HDMI gjennomgang som kan gå til en multiview-skjerm i studio. Kobles til en egen USB 3-port direkte på hovedkortet, ikke via hub. Forsinkelsen er ikke oppgitt og måles i setup-hjelperen |
| Skjermer | Teknikerskjerm på PC-en. Touch-skjerm ved bordet: iiyama ProLite T2254MSC-B2AG (21,5″, 1920 × 1080, 10-punkts touch over USB, HDMI og DisplayPort). Kortleseren kobles i skjermens USB-hub, så én USB-kabel til PC-en tar både touch og kort |
| Nett | Eget switch eller VLAN for studio, fast IP på alt, ingen DHCP for utstyr |
| Strøm | UPS for PC, ATEM, RØDECaster og switch |

**IP-plan (forslag):**

| Enhet | IP |
| --- | --- |
| ATEM | 10.10.10.10 |
| C1 Canon CR-N300 | 10.10.10.21 |
| C2–C4 OBSBOT | 10.10.10.22–24 |
| C5 fugleperspektiv (hvis IP) | 10.10.10.25 |
| C7 halvtotal | 10.10.10.27 |
| Pearl Nexus | 10.10.10.30 |
| Regi-PC | 10.10.10.40 |
| Touch-nettbrett (hvis brukt) | 10.10.10.50 |

## 3. Programvare

Programmet er delt i flere prosesser, slik at klippingen fortsetter på lyd alene hvis bildeanalysen stopper. En supervisor kjører som Windows-tjeneste og restarter det som faller ut.

**Prosesser (D-042, D-063: `stt` er tatt ut):** `core` (regimotor, API, skjermer), `audio-capture` (lyd fra RØDECaster via ASIO, ADR-0014), `vision` (multiview og bildeanalyse) og `atem-bridge` (Node.js med `atem-connection`, ADR-0012), alle under `supervisor`. ADR-0012 og ADR-0014 er akseptert (D-046); `audio-capture` sender målinger, ikke rå lyd, til `core`. Tegningen under viser den opprinnelige inndelingen.

&#91;embedded content: programvare · prosesser og moduler på regi-PC-en\]

Videolaget sender resultater til regi-core over lokal ZeroMQ (pub/sub). Skjermene er nettsider som serveres av regi-core og får live-data over WebSocket.

### 3.1 Stack

| Lag | Valg | Merknad |
| --- | --- | --- |
| Språk | Python 3.12, asyncio, mypy strict | Alle modellene og bibliotekene finnes her |
| Pakker | `uv` med låsefil; egen Python i app-mappen | Samme installasjon hver gang |
| Lyd | PortAudio med ASIO (f.eks. `sounddevice`), `numpy` | 16 kHz per kanal, 30 ms blokker; 10 ms rammer for frasegrenser |
| Tale-deteksjon | Silero VAD (ONNX) | CPU |
| Frasegrenser | Pause, energi og tonehøyde per mic (egen kode, YIN-basert tonehøyde) | CPU |
| Bilde | OpenCV eller FFmpeg (DirectShow) for capture; ONNX Runtime med CUDA/TensorRT | DirectML som reserve |
| Modeller | SCRFD eller YuNet (ansikt), MediaPipe Face Landmarker (munn, hode, smil), Light-ASD (taler) | Lagres i `models/` med versjon og sjekksum |
| Live tekst (bryter) | **Tatt ut av v1 (D-063).** Var: NB-Whisper via whisper.cpp eller ONNX | – |
| Turbytte (bryter) | **Tatt ut av v1 (D-063).** Var: Voice Activity Projection | – |
| Kortleser | `pyserial` mot ELATEC TWN3 i virtuell COM-port-modus | UID leses lokalt og forlater aldri motoren |
| Pålogging | `httpx` mot kort-API med tjenestenøkkel | 3 s tidsavbrudd, ingen hurtigbuffer av kortnummer |
| Intern meldingsbuss | ZeroMQ pub/sub | audio-capture, vision og atem-bridge → core |
| Server | FastAPI + uvicorn, Pydantic v2 for alle modeller | Samme modeller brukes i API og konfig |
| Enhetsklienter | `httpx` (Companion, Pearl, Canon XC), egen UDP-klient (VISCA), `python-osc`; ATEM leses og styres av `atem-bridge` med `atem-connection` (ADR-0012; PyATEMMax var tidligere forslag) | Kø, tidsavbrudd, gjenoppkobling og kretsbryter per enhet |
| Lagring | YAML for oppsett (i git), SQLite (WAL) for kjøredata og økthistorikk, JSON-linjer for logg | Logg roteres daglig, beholdes 30 dager |
| Web-UI | React + TypeScript + Vite, bygget statisk | Tre visninger: `touch`, `tech`, `tech/setup` |
| Drift | WinSW for tjenester, Edge i kiosk-modus med tilordnet tilgang for touch | Se seksjon 9 |
| Tester | pytest, simulator, avspilling av opptatte spor, Playwright for skjermene | Se seksjon 10 |

### 3.2 Mappestruktur

Hele filstrukturen for repo og regi-PC er beskrevet i seksjon 12.2. Kort fortalt ligger koden under `src/cutcut/` med én mappe per modul (core, audio, vision, stt, session, devices, health, setup, api, supervisor), skjermene under `ui/apps/`, og alt som er spesielt for ett studio i et eget studio-repo under `site/<studio>/`.

Hver mappe har en `README.md` med ansvar, inn- og utdata og akseptansekriterier fra seksjon 10, slik at en AI-utvikler kan bygge én modul av gangen.

## 4. Show-oppsett og konfigurasjon

Et show-oppsett er én YAML-fil som beskriver deltakere, kameraer, vinkler, layouter og regelverdier. Touch-skjermen velger og endrer oppsettet; teknikeren kan redigere alt. Filen valideres mot et Pydantic-skjema ved lasting, og motoren starter ikke med ugyldig oppsett.

```yaml
# site/<studio>/shows/podcast-standard.yaml
id: podcast-standard
name: "Podcast standard"
version: 4                      # økes ved hver lagring, eldre versjoner beholdes
participants:                   # 1–4 stk, rekkefølge = plass ved bordet
  - { id: P1, name: "Vert",    mic: M1, camera: C1, role: host }
  - { id: P2, name: "Gjest A", mic: M2, camera: C2, role: guest }
  - { id: P3, name: "Gjest B", mic: M3, camera: C3, role: guest }
cameras:
  C1: { driver: canon_xc, ip: 10.10.10.21, atem_input: 1, presets: { tight: 1, wide: 2 }, slow_zoom: false }
  C2: { driver: obsbot,   ip: 10.10.10.22, atem_input: 2, presets: { tight: 1, wide: 2 }, slow_zoom: false }
  C3: { driver: obsbot,   ip: 10.10.10.23, atem_input: 3, presets: { tight: 1, wide: 2 }, slow_zoom: false }
  C5: { driver: none,     atem_input: 5, role: bird }          # fast fugleperspektiv
content:
  atem_input: 6
  audio_mic: M5                 # laptop-lyd på RØDECaster fader 5
features:                       # grunnmodus er alltid på; dette er bryterne i 5.13
  bird: true
  content: true
  video_confirm: false
  reactions: false
  framing_variety: false
  slow_zoom: false
  layouts: false
  live_transcript: false
  turn_prediction: false
layouts:                        # gjelder bare når features.layouts er på
  pip_speaker_content: false
  pip_two_people: false
  quad_four: false
  quad_three_content: false
rules_preset: standard          # rolig | standard | energisk
rules_override:                 # bare verdier som avviker fra preset
  T7_reaction_after_s: 18
color:
  reference_camera: C1
  saved_at: 2026-10-20T09:12:00+02:00
  values: { C2: { kelvin: 5450, r: +6, b: -4 }, C3: { kelvin: 5600, r: 0, b: +3 } }
```

**Regler for oppsettet:**

- Antall deltakere er alltid det som står i oppsettet. Videolaget kan bare advare (for eksempel «tomt bilde på C3»), aldri endre antallet selv.
- En deltaker uten kamera er ikke tillatt. Et kamera kan ha flere vinkler via presets.
- `C5` (fugleperspektiv) er påkrevd fra v1. `C7` er valgfritt.
- Endringer under sending lagres som ny versjon og tas i bruk ved neste kutt.

## 5. Regimotor

Motoren velger først modus ut fra antall deltakere og om content er aktivt, og bruker så faste regler i fast prioritetsrekkefølge. Hver beslutning lagres med regel-ID og målte verdier, og vises i loggen.

### 5.1 Moduser

Modus byttes automatisk når content blir aktivt eller forsvinner. Antall deltakere kommer fra show-oppsettet.

| Modus | Deltakere | Content | Bildeutvalg | Krysstale | Stillhet | Ping-pong | Layouter (hvis slått på) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `N1` | 1 | nei | `CU:P1`, `WIDE`, `BIRD` | – | `WIDE`, ellers `BIRD` | – | – |
| `N1C` | 1 | ja | + `CONTENT` | – | `CONTENT` | – | `PIP:P1+CONTENT` |
| `N2` | 2 | nei | `CU:P1–2`, `WIDE`, `BIRD` | `WIDE`, ellers `BIRD` | `BIRD` | `WIDE`/`BIRD` | `PIP:P1+P2` |
| `N2C` | 2 | ja | + `CONTENT` | `WIDE`/`BIRD` | `CONTENT` | `WIDE`/`BIRD` | `PIP:Px+CONTENT`, `PIP:P1+P2` |
| `N3` | 3 | nei | `CU:P1–3`, `BIRD` | `BIRD` | `BIRD` | `BIRD` | `PIP:Px+Py` |
| `N3C` | 3 | ja | + `CONTENT` | `BIRD` | `CONTENT` | `BIRD` | `QUAD3C`, `PIP:Px+CONTENT` |
| `N4` | 4 | nei | `CU:P1–4`, `BIRD` | `BIRD` | `BIRD` | `BIRD` | `QUAD4`, `PIP:Px+Py` |
| `N4C` | 4 | ja | + `CONTENT` | `BIRD` | `CONTENT` | `BIRD` | `PIP:Px+CONTENT` |

`WIDE` krever kamera `C7`. Finnes det ikke, brukes `BIRD`. Når en layout er slått på og passer, erstatter den bildet i kolonnen «Ping-pong» eller «Krysstale».

**Kun lyd** er en egen modus `A`: motoren klipper ikke, kameraene står i ro, og ATEM viser mediaspilleren med «Kun lyd»-grafikk på program hele opptaket. Lydreglene kjører fortsatt, slik at mic-stripene og live tekst virker.

### 5.2 Prioritetsrekkefølge

Motoren går gjennom stegene hvert 30. millisekund og stopper ved første steg som gir et kutt.

1. **Overstyring:** manuelt kutt, LÅS og AUTO AV vinner alltid. Etter et manuelt kutt venter motoren 5 s før den tar egne beslutninger.
2. **Sikkerhet (`S`):** ingen kutt hvis det bryter minste bildelengde, ugyldig bilde eller grensen på ett kutt per sekund.
3. **Content (`C`):** ny slide, video eller tapt signal.
4. **Krysstale og latter (`T5`, `B2`, `B4`):** til modusens krysstale-bilde.
5. **Taler (`T2`, `T4`):** ny bekreftet taler legges på preview og tas til program på neste kuttpunkt (5.9–5.10).
6. **Variasjon (`T7`, `B5`, og `R` hvis slått på):** reaksjonsbilde eller kort fugleperspektiv under lange svar.
7. **Stillhet (`T8`, `B3`):** til modusens stillhetsbilde.

Hold og release (5.11) gjelder for alle stegene unntatt overstyring og tapt content-signal.

### 5.3 Tale-regler (`T`)

Verdiene er for forhåndsvalget Standard; Rolig og Energisk er beskrevet i fanen «Evaluering og bakgrunn».

| ID | Regel | Standard |
| --- | --- | --- |
| `T1` | Mic er aktiv når VAD > terskel og nivået ligger over alle andre mic-er med margin | VAD 0,6 · 6 dB |
| `T2` | Ny taler må snakke sammenhengende før kutt (V1 korter ned ved munnbevegelse) | 800 ms (× 0,6) |
| `T3` | Minste bildelengde | 2,5 s |
| `T4` | Avbrudd kortere enn dette ignoreres mens noen andre snakker | 1,0 s |
| `T5` | To eller flere aktive samtidig → modusens krysstale-bilde | 1,0 s |
| `T6` | Mange bytter mellom personer → modusens ping-pong-bilde | 4 bytter per 10 s |
| `T7` | Reaksjonsbilde av en lytter i 2,5 s; i `N1` vinkelbytte mellom `CU` og `WIDE` | etter 15 s |
| `T8` | Ingen aktiv mic → modusens stillhetsbilde | 3 s |
| `T9` | Venter på kort pause hos taleren før kutt | maks 300 ms |
| `T12` | Vekt for vert når to er like sterke | × 1,1 |

### 5.4 Fugleperspektiv (`B`)

Fugleperspektivet er etablerende bilde og pusterom, og skal brukes bevisst, ikke som standard-reserve.

| ID | Regel | Standard |
| --- | --- | --- |
| `B1` | Åpning: sendingen starter på `BIRD`, og et kort `BIRD` brukes etter hver content-blokk | 4 s, deretter 3 s |
| `B2` | Krysstale med tre eller flere aktive → `BIRD` | 1,0 s |
| `B3` | Lang stillhet → `BIRD` (i `N1`/`N2` først `WIDE` hvis den finnes) | 3 s |
| `B4` | Latter: to eller flere ler (latter i lyd eller smil i bildet) → `BIRD` | 2–4 s |
| `B5` | Variasjon: kort `BIRD` i talerens pause under lange svar, men maks andel av tiden | 3–5 s, maks 15 %, minst 45 s mellom |

### 5.5 Content (`CT`)

Content er laptopen på inngang 6. Motoren finner ut om den er i bruk ved å se på multiview-ruta (seksjon 6.2), og bruker laptop-lyden på fader 5 som ekstra signal.

| ID | Regel | Standard |
| --- | --- | --- |
| `CT1` | Content regnes som aktivt når ruta har signal, ikke er svart og ikke viser «ingen signal» | i 2 s |
| `CT2` | Ny slide (stor bildeendring, så stille bilde) → `CONTENT`, eller `PIP:Px+CONTENT` hvis `L1` er på | 6 s |
| `CT3` | Video i content (vedvarende bevegelse eller laptop-lyd på `M5`) → hold `CONTENT` | maks 60 s |
| `CT4` | Statisk content: tilbake til taler, og et kort besøk igjen hvis den fortsatt er aktiv | etter 6 s; besøk 4 s hvert 45 s (av som standard) |
| `CT5` | Laptop-lyd aktiv (`M5`) gir content prioritet over taler | på |
| `CT6` | Aldri `CONTENT` under krysstale eller latter. Forsvinner signalet mens content er på lufta, kuttes det straks til taler eller `BIRD` | på |

### 5.6 Layouter (`L`) – av som standard

Layoutene er bygget som makroer i ATEM (seksjon 7.2). Motoren trykker bare på Companion-knappen, og regner layouten som på lufta først når ATEM-tilstanden bekrefter det.

| ID | Layout | Når | Modus |
| --- | --- | --- | --- |
| `L1` | `PIP:Px+CONTENT` | Taler snakker over 4 s og content er aktivt og vist siste 20 s | `N1C`–`N4C` |
| `L2` | `PIP:Px+Py` | Ping-pong mellom to bestemte personer, i stedet for `WIDE`/`BIRD` | `N2`–`N4C` |
| `L3` | `QUAD4` | Tre eller flere ulike talere siste 10 s, eller krysstale med tre eller flere | `N4` |
| `L4` | `QUAD3C` | Som `L3`, men med content aktivt og tre deltakere | `N3C` |

En layout står minst 6 s, og samme layout brukes ikke to ganger på rad innen 30 s.

### 5.7 Sikkerhet (`S`)

| ID | Regel |
| --- | --- |
| `S1` | Ikke kutt til et kamera som beveger seg, eller har flyttet seg siste 0,5 s (`V5`) |
| `S2` | Ikke kutt til et bilde uten gyldig ansikt (`V2`); bruk modusens reservebilde |
| `S3` | Hard grense: maks ett kutt per sekund, uansett regel |
| `S4` | Mister motoren lyden i mer enn 2 s: kutt til `BIRD`, sett AUTO på pause og varsle |
| `S5` | Mister motoren Companion: prøv direkte ATEM-kutt; feiler det også, stopp og varsle |
| `S6` | En mic som er aktiv, men mangler i hovedmiksen (dempet eller nede på RØDECaster), regnes som dempet: ingen kutt til den personen (D-035; avhenger av Q24) |

### 5.8 Beslutningsobjekt

Alle beslutninger, også de som venter, sendes som samme objekt til logg og skjermer:

```json
{
  "ts": "2026-10-20T19:04:11.320+02:00",
  "mode": "N3C",
  "action": "cut",
  "shot": "CU:P2",
  "rule": "T2",
  "reason": "Gjest A aktiv 0,52 s (krav 0,48 s), munn 0,81, 12 dB over de andre",
  "measures": { "run_ms": 520, "vad": 0.88, "mouth": 0.81, "dominance_db": 12 },
  "blocked_by": null,
  "companion": { "page": 10, "row": 0, "col": 1 }
}
```

`action` er `cut`, `wait` eller `hold`. Ved `wait` sier `blocked_by` hvilken regel som holder igjen, for eksempel `T3`.

### 5.9 Preview først, så program

Motoren klipper ikke rett på program i normal drift. Den legger neste bilde på preview så snart det finnes en kandidat, og tar det til program på riktig tidspunkt. Operatøren ser derfor hele tiden hva motoren tenker å gjøre, både i multiviewens store preview-rute og i teknikervinduet.

| Tilstand | Betyr | Overgang |
| --- | --- | --- |
| `IDLE` | Ingen kandidat; preview viser modusens reservebilde | → `ARMED` når en ny taler har vært aktiv halve `T2`, eller en `CT`-, `B`- eller `T7`-regel ønsker bytte |
| `ARMED` | Kandidaten ligger på preview | → `READY` når alle krav er oppfylt; → `IDLE` hvis kandidaten faller bort |
| `READY` | Alt er klart, venter på kuttpunkt (5.10) | → `TAKE` på kuttpunkt; → `IDLE` hvis ny taler slutter før kuttpunktet |
| `TAKE` | Companion trykker CUT (eller MIX for layouter) | → `IDLE` |

| ID | Regel | Standard |
| --- | --- | --- |
| `PV1` | Preview byttes ikke oftere enn dette, så multiview ikke blinker | 0,5 s |
| `PV2` | Kamera på preview behandles som på lufta: det beveges ikke | på |
| `PV3` | Med videolag på: preview-ruta (ca. 960 × 540 piksler, større enn de små rutene) må vise gyldig ansikt og stillestående bilde før `TAKE` | på |
| `PV4` | Overstyring og `S`-regler kan kutte direkte på program | på |

### 5.10 Kuttpunkt: mellom setninger

Taleren bekreftes på lyd, men selve kuttet tas på et naturlig sted i samtalen. Motoren kutter helst i overgangen mellom to personer, og aldri midt i et ord.

| ID | Kuttpunkt | Standard |
| --- | --- | --- |
| `K1` | Turbytte: forrige taler er stille. Ta straks når ny taler er bekreftet | pause ≥ 300 ms |
| `K2` | Overlapp: forrige taler snakker fortsatt. Vent på frasegrense hos forrige taler | pause ≥ 250 ms, eller fallende tonehøyde + pause ≥ 150 ms |
| `K3` | Maks ventetid. Snakker den nye fortsatt, tas kuttet; ellers avbrytes det | 1,5 s |
| `K4` | Kutt som ikke skyldes ny taler (reaksjon, fugleperspektiv, vinkelbytte) tas bare i talerens pause, og tilbake når taleren starter ny frase | pause ≥ 250 ms |

Frasegrenser finnes per mic fra pauselengde, energifall og tonehøyde (fallende tonehøyde mot slutten av en setning). Analysen kjører på 10 ms rammer i lydmodulen og legges i beslutningsobjektet som `phrase_end`.

### 5.11 Hold og release

Et kutt er en beslutning, og bildet skal få stå. Disse reglene gjør klippingen rolig og menneskelig uten å bli treg.

| ID | Regel | Standard |
| --- | --- | --- |
| `H1` | Første sekunder etter et kutt kreves sterkere bevis for nytt taler-kutt (gjelder ikke content og sikkerhet) | `T2` × 1,5 i 5 s |
| `H2` | Ikke tilbake til forrige bilde for raskt | 4 s |
| `H3` | Release: når taleren på lufta slutter, står bildet før motoren går til stillhets- eller fugleperspektiv-bilde. Ny taler kan fortsatt komme inn etter `T2` | 1,0 s |
| `H4` | Etter reaksjonsbilde eller fugleperspektiv-innslag går motoren tilbake til samme taler, ikke til en ny vinkel | på |

### 5.12 Roller: vert og gjest

Hver deltaker har rollen `host` eller `guest`, satt i show-oppsettet og i veiviseren. Det kan være flere verter. Rollen endrer reglene slik en bilderegissør tenker:

| Gjelder | Vert | Gjest |
| --- | --- | --- |
| Prioritet når to er like sterke (`T12`) | × 1,1 | × 1,0 |
| Korte innskudd («ja», «mm», «nettopp») mens den andre rollen snakker | Gir aldri kutt under 1,5 s | `T4` som vanlig |
| Minste bildelengde (`T3`) | Standard | + 1 s, så svarene får stå |
| Reaksjonsbilde under lange svar | Gjesten som blir snakket til, ellers den som snakket sist | Verten først |
| Åpning (`B1`) | `BIRD`, så verten | – |

### 5.13 Grunnmodus og brytere

Grunnmodus er lyd, regler, preview først, kuttpunkt, hold og release. Alt annet er brytere per show, og står av som standard bortsett fra fugleperspektiv og content. Teknikeren kan slå dem av og på under sending.

| Bryter | Standard | Gjør | Krever |
| --- | --- | --- | --- |
| `bird` (`B1`–`B5`) | på | Fugleperspektiv som åpning, pusterom og ved latter | `C5` |
| `content` (`C`) | på | Laptop som content | Inngang 6 |
| `video_confirm` (`V1`, `V2`, `V5`, `PV3`) | av | Bildet bekrefter taler og gyldig bilde | Videolag |
| `reactions` (`R`) | av | Reaksjonsklipp ved nikk og latter | Videolag |
| `framing_variety` (`F`) | av | Kamera off air veksler mellom tett og videre utsnitt | PTZ |
| `slow_zoom` (`Z`) | av | Langsom zoom under lange svar | PTZ som tåler sakte zoom |
| `layouts` (`L`) | av | PiP og quad | ATEM-makroer |
| `live_transcript` | av | Live tekst per mic | GPU |
| `turn_prediction` | av | Forvarsel om turbytte | Eksperimentell |
| ai\_tracking (AT) | av | Kameraet følger personen selv, per kamera | OBSBOT Tail 2 med OSC |

**Reaksjonsklipp (`R`):**

| ID | Regel | Standard |
| --- | --- | --- |
| `R1` | Lytter nikker, smiler tydelig eller ler (bildet + lytterens mic) mens taleren har snakket lenge → reaksjonsbilde i talerens neste pause (`K4`) | taler ≥ 6 s, bilde 2–3 s |
| `R2` | Begrensning | maks 1 per 20 s, aldri på svar under 6 s |
| `R3` | Begynner lytteren å snakke, gjelder taler-reglene, ikke reaksjon | på |

**Utsnittsvariasjon (`F`):**

| ID | Regel | Standard |
| --- | --- | --- |
| `F1` | Når et kamera går av program og preview, velges neste utsnitt vekselvis tett eller videre, så samme person ikke får samme utsnitt to ganger på rad | veksling |
| `F2` | Bevegelsen kjøres med lav fart og må være ferdig og stille (`V5`, `S1`) før kameraet kan legges på preview | ferdig + 0,5 s |
| `F3` | Kamera som er kandidat til neste kutt flyttes ikke | på |

**Langsom zoom (`Z`):**

| ID | Regel | Standard |
| --- | --- | --- |
| `Z1` | Bare på bilde der samme taler har stått en stund; zoom inn litt over lang tid | etter 3 s, maks 10 % over 10–20 s |
| `Z2` | Stopper straks et annet bilde legges på preview; aldri samtidig med pan eller tilt | på |
| `Z3` | Slås på per kamera, fordi laveste zoomfart er ulik mellom modeller. Må testes på OBSBOT og Canon før bruk | per kamera |

**AI-tracking (`AT`):** kameraet følger personen selv. Nyttig for en programleder som står og går, en gjest som lener seg mye, eller et halvtotal-bilde som skal holde én person i bildet. Slås på per kamera, aldri for fugleperspektivet.

| ID | Regel | Standard |
| --- | --- | --- |
| `AT1` | Tracking slås på eller av for ett kamera fra teknikervinduet, Stream Deck eller show-typen (`ai_tracking: [C2]`) | av |
| `AT2` | Når tracking slås på, settes kameraet først til enkeltperson, tracking-fart «lat», auto-zoom av og «Only Me» av, slik at bevegelsen blir rolig og zoomen fortsatt styres av CutCut | på |
| `AT3` | Mens tracking er på, gjør CutCut ingen egne bevegelser på kameraet: utsnittsjustering (`V4`), vekslende utsnitt (`F`), langsom zoom (`Z`) og presets er sperret | på |
| `AT4` | `S1` (ikke kutt til kamera i bevegelse) gjelder fortsatt, men med toleranse for rolig tracking: kameraet regnes som stille under 3° per sekund | 3°/s |
| `AT5` | Når tracking slås av, står kameraet der det er; CutCut henter ikke preset før kameraet er av program og preview | på |
| `AT6` | Tracking er alltid av når en økt avsluttes, og ved oppstart av CutCut | på |

Kommandoen for av og på (`SetAiEnable`) står ikke i OBSBOT sin OSC-tabell, men brukes av Companion sin offisielle OBSBOT-modul fra versjon 1.2.0 (oktober 2026). Den bekreftes på kameraet i setup-hjelperen før bryteren kan slås på. Kameraet sier ikke tilbake om tracking er på, så CutCut kontrollerer det ved å lese posisjonen: med tracking av skal kameraet stå stille (`H-CAM-MOVE`).

**Live tekst (tatt ut av v1, D-063):** teksten kommer flere sekunder for sent til å hjelpe klippingen, og klippingen bygger på lydanalysen. Teksten under står som bakgrunn. Hver mic transkriberes for seg med [NB-Whisper](https://huggingface.co/NbAiLabBeta/nb-whisper-medium/blob/4b385df7b3683972d66b7165837267cdd52f978f/README.md?code=true) fra Nasjonalbiblioteket (Apache 2.0, størrelser fra tiny til large, finnes blant annet som ONNX og whisper.cpp). Da er det alltid kjent hvem som sa hva. Strømming med Whisper gir noen sekunders forsinkelse; [Whisper-Streaming](https://arxiv.org/html/2307.14743) målte 3,3 s i snitt på engelsk med stor modell. Teksten er derfor for sen til å styre kuttpunkt, og brukes bare til tre ting:

- live tekst per person i teknikervinduet, lagret med beslutningsloggen;
- forvarsel: sier en vert navnet til en gjest og stiller et spørsmål, legges gjesten tidlig på preview, men kuttet krever fortsatt `T2`;
- valgfrie markører i Pearl-opptaket når verten stiller et nytt spørsmål.

Live tekst kjører i egen prosess med lavest prioritet, og stopper selv hvis GPU-en trengs til videolaget.

**Forvarsel om turbytte (tatt ut av v1, D-063):** [Voice Activity Projection](https://arxiv.org/html/2401.04868v1) spår hvem som snakker de neste 2 sekundene fra lyden til to personer, og nådde 76 % balansert treffsikkerhet i sanntid. Modellen er ikke trent på norsk og fungerer bare for to personer. Den brukes derfor bare til å legge en kandidat tidligere på preview, aldri til å ta et kutt.

## 6. Videolaget

Videolaget leser multiviewen fra ATEM, deler den i ruter etter rutekartet, og sender resultater per rute til motoren 10–15 ganger i sekundet. Det tar aldri beslutninger selv.

### 6.1 Ruter og analyse

Rutekartet ligger i `site/<studio>/equipment/multiview_map.yaml` med koordinater i andel av bildet (0–1), slik at det virker uansett oppløsning. Hver rute kuttes 4 % inn på alle sider for å fjerne tally-ramme og navneskilt.

| Rute | Kilde | Analyse | Bilder/s |
| --- | --- | --- | --- |
| 1–4 | `C1`–`C4` | Ansikt, munnbevegelse, hoderetning, smil, utsnittsfeil, bevegelse | 15 |
| 5 | `C5` fugleperspektiv | Antall personer ved bordet, smil og latter, bevegelse | 5 |
| 6 | `LAPTOP` | Content-deteksjon (6.2) | 5 |
| 7 | `C7` | Som rute 1–4, uten munn | 5 |
| 8 | SuperSource | Hvilken layout som er klar (sammenlignes med referansebilder) | 2 |
| PGM | Program | Bekrefter hva som faktisk er på lufta | 5 |

### 6.2 Content-deteksjon

Content-tilstanden er én av fire, og bestemmes bare fra rute 6 og laptop-lyden:

| Tilstand | Slik måles det |
| --- | --- |
| `NO_SIGNAL` | Ruta er nesten helt svart, eller matcher ATEM sitt «ingen signal»-bilde |
| `STATIC` | Signal, lite endring mellom bilder over 2 s |
| `NEW_SLIDE` | Stor endring (over 15 % av pikslene), etterfulgt av stille bilde i 0,5 s |
| `VIDEO` | Vedvarende bevegelse over 1 s, eller laptop-lyd på `M5` |

En laptop som viser skrivebord eller skjermsparer gir `STATIC`. Derfor kan teknikeren og verten slå content av med én knapp, uansett hva ruta viser.

### 6.3 Deltakere og fugleperspektiv

Fugleperspektivet brukes til å telle personer ved bordet. Avviker antallet fra show-oppsettet i mer enn 10 s, vises en advarsel på begge skjermene, men oppsettet endres ikke. Smil hos to eller flere i fugleperspektivet støtter latter-regelen `B4`.

### 6.4 Farge

Fargemåling skjer bare på forespørsel fra oppsett-skjermen. Systemet finner gråkortet i hver rute, måler snittfarge og lysstyrke, og justerer kameraene mot referansekameraet i 3–5 runder. Kameraer på lufta justeres aldri.

### 6.5 Bilde-regler (`V`)

| ID | Regel | Standard |
| --- | --- | --- |
| `V1` | Munnbevegelse i riktig kamera korter ned `T2`; aktiv mic uten munnbevegelse i 400 ms regnes som lekkasje | × 0,6 |
| `V2` | Gyldig bilde: ansikt funnet, innenfor bildet, riktig størrelse | ±25 % av målstørrelse |
| `V3` | Reaksjonsbilde (`T7`) velger lytteren med høyest reaksjon (smil, nikk, bevegelse) | siste 3 s |
| `V4` | Utsnitt rettes med små steg mens kameraet er off air; fryses når kameraet er kandidat til neste kutt | feil > 8 % av bildehøyden |
| `V5` | Vinkel er gyldig først når bildet har stått stille | 0,5 s |
| `V6` | Taleren ser mot en person: litt høyere prioritet for den personen (eksperimentelt, av som standard) | × 1,1 |

### 6.6 Melding til motoren

```json
{
  "topic": "vision.tile",
  "ts": "2026-10-20T19:04:11.280+02:00",
  "tile": 2, "source": "C2",
  "face": { "found": true, "box": [0.31, 0.18, 0.42, 0.61], "size_ok": true },
  "mouth": 0.81, "smile": 0.10, "head_yaw_deg": -12,
  "moving": false, "framing_error": 0.03,
  "asd": 0.86
}
```

Content sender `{"topic": "vision.content", "state": "NEW_SLIDE", "changed_ratio": 0.42}`. Mangler meldinger fra videolaget i over 1 s, går motoren over til bare lyd og viser det på skjermene.

## 7. Integrasjoner

Motoren snakker med fire typer utstyr: Companion for alle kutt og layouter, ATEM direkte bare for å lese tilstand, kameraene direkte over IP, og Pearl over REST. Hver integrasjon har tidsavbrudd, automatisk gjenoppkobling og egen status på skjermene.

### 7.1 Companion: side 10 «REGI»

Siden er laget for et Stream Deck XL (8 × 4). Side 10 brukes av motoren; side 11 er for mennesker. Kall: `POST http://127.0.0.1:8000/api/location/10/<rad>/<kol>/press`. Companion kjører på regi-PC-en, og motoren kaller den lokalt; Companion sitt nettgrensesnitt er ikke åpent fra andre maskiner (12.4).

| Rad | Kol 0 | Kol 1 | Kol 2 | Kol 3 | Kol 4 | Kol 5 | Kol 6 | Kol 7 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 – til preview | `C1` | `C2` | `C3` | `C4` | `BIRD` | `LAPTOP` | `C7` | SuperSource |
| 1 – PiP content | `PIP:P1+CONTENT` | `PIP:P2+CONTENT` | `PIP:P3+CONTENT` | `PIP:P4+CONTENT` | Layout av | – | – | – |
| 2 – PiP/quad | `PIP:P1+P2` | `PIP:P1+P3` | `PIP:P1+P4` | `PIP:P2+P3` | `PIP:P2+P4` | `PIP:P3+P4` | `QUAD4` | `QUAD3C` |
| 3 – take | TAKE CUT | TAKE MIX | – | – | – | – | – | – |

Operatørknappene ligger på side 11: AUTO av/på, LÅS, BIRD nå, content av/på, REC start, REC stopp, markør, status, og direkte programkutt `C1`–`C7` for nødbruk.

Rad 0 setter preview med ATEM-modulen. Rad 1–2 kjører ATEM-makroer som bygger layouten og legger SuperSource på preview. Rad 3 tar preview til program med cut (taler) eller mix (layouter). Side 11 kaller motorens API via Generic HTTP, og Pearl via Companion sin [Epiphan Pearl-modul](https://github.com/bitfocus/companion-module-epiphan-pearl) (start/stopp opptak, markør).

**Custom variables som motoren skriver** (vises på Stream Deck og brukes i Companion-feedback): `regi_shot`, `regi_rule`, `regi_reason`, `regi_mode`, `regi_auto`, `regi_health`. Kall: `POST /api/custom-variable/<navn>/value?value=<verdi>`.

### 7.2 ATEM-makroer

Layoutene lages i ATEM Software Control og lagres som makroer med fast nummer og navn. Hver makro setter SuperSource-bokser (eller DVE-nøkkel) og legger layouten på preview; motoren tar den til program med TAKE MIX. Motoren endrer aldri geometri selv.

| Makro | Navn | Innhold |
| --- | --- | --- |
| 10–13 | `PIP_P1_CONTENT` … `PIP_P4_CONTENT` | Laptop stor, deltakerens kamera i hjørnet |
| 20–25 | `PIP_P1_P2` … `PIP_P3_P4` | To deltakere side om side |
| 30 | `QUAD4` | `C1`–`C4` i fire ruter |
| 31 | `QUAD3C` | `C1`–`C3` + laptop |
| 40 | `LAYOUT_RESET` | Nøkler av, SuperSource tilbake til standard |

Makronumrene og navnene ligger også i `site/<studio>/equipment/atem_macros.yaml`, og motoren sjekker ved oppstart at alle finnes i ATEM.

**SuperSource-geometri.** Alle layoutene bygges med SuperSource, som legger opptil fire bokser over en bakgrunn. ATEM sitt koordinatsystem er −48 til +48 i bredden og −27 til +27 i høyden, med (0, 0) midt i bildet, og en boks med størrelse 1,0 fyller hele bildet. Verdiene under er startpunkter; de justeres ved første oppsett og lagres i `site/<studio>/equipment/atem_layouts.yaml`.

| Layout | Bakgrunn | Boks 1 | Boks 2 | Boks 3 | Boks 4 |
| --- | --- | --- | --- | --- | --- |
| `PIP:Px+CONTENT` | Mediaspiller 2 (merkevarebakgrunn) | Laptop · str. 0,66 · x −14,3 · y 0 | Deltaker · str. 0,28 · x 32,6 · y 0 | av | av |
| `PIP:Px+Py` | Mediaspiller 2 | Px · str. 0,5 · x −24 · y 0 | Py · str. 0,5 · x 24 · y 0 | av | av |
| `QUAD4` | Mediaspiller 2 | C1 · 0,5 · (−24, 13,5) | C2 · 0,5 · (24, 13,5) | C3 · 0,5 · (−24, −13,5) | C4 · 0,5 · (24, −13,5) |
| `QUAD3C` | Mediaspiller 2 | C1 · 0,5 · (−24, 13,5) | C2 · 0,5 · (24, 13,5) | C3 · 0,5 · (−24, −13,5) | Laptop · 0,5 · (24, −13,5) |

To-skuddet gir svarte felt over og under bildene (letterbox), som fylles av bakgrunnen. Vil dere heller ha to høye halvbilder, beskjæres boksene til smalere utsnitt; det avgjøres ved test. Hvilken boks som ligger øverst når de overlapper, sjekkes ved første oppsett.

**Slik lages en makro** (setup-hjelperen viser stegene og sjekker resultatet):

1. Åpne ATEM Software Control, gå til *Macros* og velg ledig plass med nummeret fra tabellen over.
2. Trykk *Record*, gi makroen navnet fra tabellen, og gjør i rekkefølge: slå på og plasser boksene som i tabellen; velg bakgrunn; sett **Preview** til SuperSource. Ikke trykk CUT eller AUTO: motoren tar layouten til program selv.
3. Trykk *Stop Record*.
4. Lagre ATEM-oppsettet (*File → Save As*) og legg filen i `site/<studio>/equipment/atem/` i git.
5. Setup-hjelperen kjører makroen, leser SuperSource-tilstanden fra ATEM og sammenligner med `atem_layouts.yaml`. Avvik over 0,5 enheter i posisjon eller 0,02 i størrelse vises som feil.

`LAYOUT_RESET` slår av alle bokser og setter preview tilbake til fugleperspektivet. «Kun lyd»-grafikken lastes inn i mediaspiller 1, og merkevarebakgrunnen i mediaspiller 2.

### 7.3 Kameradrivere

Alle drivere implementerer samme grensesnitt. Funksjoner et kamera ikke har, svarer `Unsupported`, og GUI-et skjuler da knappen.

```python
class CameraDriver(Protocol):
    id: str                                   # "C2"
    async def connect(self) -> None: ...
    async def status(self) -> CameraStatus: ...         # online, modus, siste feil
    async def recall_preset(self, n: int, speed: float = 0.5) -> None: ...
    async def store_preset(self, n: int) -> None: ...
    async def nudge(self, pan: float, tilt: float, zoom: float) -> None: ...  # små relative steg, -1..1
    async def position(self) -> PTZPosition | None: ...
    async def set_white_balance(self, kelvin: int | None = None,
                                r: int | None = None, b: int | None = None) -> None: ...
    async def set_exposure(self, iris: float | None = None, gain_db: float | None = None,
                           shutter: str | None = None) -> None: ...
    async def set_auto_tracking(self, on: bool) -> None: ...
```

| Driver | Transport | Merknad |
| --- | --- | --- |
| `obsbot` | VISCA over IP (UDP 52381) for bevegelse og presets; OSC (UDP 57110/57120) for fargetemperatur og eksponering; begge direkte til kameraet | Kommandotabell fra OBSBOT sin VISCA-liste for Tail 2; AI-tracking via OSC |
| `canon_xc` | XC over HTTP | Kameraet må stå i manuell for farge og eksponering |
| `panasonic_aw` (fase 2) | HTTP `/cgi-bin/aw_ptz`, `/cgi-bin/aw_cam` | Minst 40 ms mellom bevegelseskommandoer |
| `sony_visca` (fase 2) | VISCA over IP, UDP 52381 | – |

Alle kommandoer går gjennom én kø per kamera. Driveren nekter bevegelse og farge på et kamera som er på program, uavhengig av hva motoren ber om.

**OBSBOT Tail 2 over VISCA** (UDP-port 52381, fra OBSBOT sin kommandotabell). Disse kommandoene dekker det driveren trenger:

| Funksjon | Kommando | Merknad |
| --- | --- | --- |
| Hent preset | `81 01 04 3F 02 pp FF` | `pp` = 00–FF |
| Lagre preset | `81 01 04 3F 01 pp FF` | Brukes bare fra setup-hjelperen |
| Preset-fart | `81 01 7E 04 1C 0p 0p FF` | 01–19; lav fart for rolige bevegelser |
| Pan/tilt til posisjon | `81 01 06 02 vv ww 0p 0p 0p 0p 0t 0t 0t 0t FF` | `vv`/`ww` = fart; brukes til små utsnittsjusteringer (`V4`, `F`) |
| Les pan/tilt | `81 09 06 12 FF` | Brukes til grenser, `S1` og status |
| Zoom til verdi | `81 01 04 47 0z 0z 0z 0z FF` | Langsom zoom (`Z`) som mange små steg |
| Zoom med fart | `81 01 04 07 2p FF` / `3p` | `p` = 0 (lav) til 7 |
| Les zoom | `81 09 04 47 FF` |  |
| Hvitbalanse-modus | `81 01 04 35 0p FF` | 5 = manuell |
| R- og B-gain | Opp/ned: `81 01 04 03 02/03 FF` og `81 01 04 04 02/03 FF`; les: `81 09 04 43 FF` og `81 09 04 44 FF` | Brukes til avlesing; kelvin settes med OSC |
| Eksponering | Modus `81 01 04 39 0p FF` (3 = manuell); gain og lukker med opp/ned; lysstyrke direkte `81 01 04 4D 00 00 0p 0q FF` | Les med `81 09 04 4C FF` (gain) og `81 09 04 4A FF` (lukker) |
| AI-tracking | Modus, fart, auto-zoom og «Only Me» under `81 01 8E 0x …` | Ingen av/på i VISCA; av/på går via OSC SetAiEnable |

AI-tracking slås av og på av CutCut med OSC (\`/OBSBOT/Camera/Tail2/SetAiEnable\`), og er av som standard (bryter \`ai\_tracking\`, 5.13). Fargetemperatur og eksponering settes med OSC direkte til kameraet, fordi VISCA mangler kelvin. Full kommandoliste for VISCA og OSC, og hva som skal testes, står i fanen Teknisk referanse. Kommandotabellene (VISCA og OSC) lagres som filer i `site/<studio>/equipment/obsbot/`, slik at driveren og testene bygges mot det samme.

### 7.4 Epiphan Pearl Nexus

Motoren leser Pearl direkte via [REST-API v2.0](https://github.com/epiphan-video/pearl_api_swagger_ui) med Basic-autentisering. Start og stopp kan gjøres både fra touch-skjermen (via motoren) og fra Stream Deck (via Companion); begge er trygge å gjenta.

| Kall | Brukes til | Intervall |
| --- | --- | --- |
| `GET /api/v2.0/recorders/status` | Opptaksstatus: `disabled`, `starting`, `started`, `stopped`, `error`, og varighet | 2 s |
| `POST /api/v2.0/recorders/control/start?ids=<id>` | Start opptak | Ved trykk |
| `POST /api/v2.0/recorders/control/stop?ids=<id>` | Stopp opptak | Ved trykk, med bekreftelse |
| `GET /api/v2.0/inputs` | Om Pearl får signal fra ATEM (`nosignal`, oppløsning) | 5 s |
| `GET /api/v2.0/system/storages` | Ledig lagring | 30 s |
| `GET /api/v2.0/system/status` | Oppetid, CPU-last og temperatur | 30 s |
| `GET /api/v2.0/system/firmware/version` | Sjekk ved oppstart | 1 gang |

**Varsler fra Pearl:** rødt ved `error` eller ingen signal på inngangen; gult ved lite lagring (under 60 minutter igjen ved gjeldende bitrate) eller høy CPU-temperatur; grønt ellers. Opptak som stopper uten at noen trykket stopp gir rødt varsel og lyd på teknikerskjermen.

### 7.5 Kortinnlogging og økter

> **Innlogging uten kort (D-057):** kortleser og kort-API tas i bruk sist. Til da står innstillingen «Innlogging» på «Start-knapp»: hvileskjermen viser en Start-knapp, og økta får brukeren «Gjest» uten Panopto-eier. Valget «Adgangskort» gir flyten under.

Brukeren holder ansattkortet mot leseren ved touch-skjermen, og systemet viser «Velkommen» med navnet. Kortnummeret brukes bare til oppslaget og lagres aldri (`I8`).

1. **Lesing:** kortleseren er en [ELATEC TWN3 MIFARE](https://www.ELATEC-rfid.com/fileadmin/Documents/Data-Sheet/elatec-twn3-mifare-data-sheet-en.pdf) med USB. Den settes i modusen *Intelligent Virtual COM Port* med ELATEC sitt verktøy TWNConfig, og et skript som sender kortnummeret som hex-tekst. Motoren leser COM-porten med `pyserial`. Da trengs ikke tastaturfokus, og et kort som skannes kan ikke havne i feil felt på skjermen. Bruk samme leseroppsett som i studioene med Crestron, så kortnummeret får samme format.
2. **Oppslag:** motoren kaller Multimediesenteret sitt API på adressen fra IT-avdelingen (settes i appen) med kortnummeret i hex og en tjenestenøkkel, med 3 s tidsavbrudd. Nøkkel og svarformat kommer senere; svaret skal gi brukernavn og visningsnavn.
3. **Økt:** ny økt opprettes, og touch-skjermen går videre til velkomst og showvalg.
4. **Feil:** «Kortet ble ikke gjenkjent» med knapp for å prøve igjen. Er kort-API-et nede, kan teknikeren tillate «Start uten innlogging», og opptaket merkes `ukjent bruker`.

**Regler for økter:**

- Bare én aktiv økt. Et nytt kort under opptak avvises med en melding; samme kort igjen gjør ingenting.
- Utlogging skjer med knappen «Ferdig, logg ut», automatisk 30 sekunder etter at opptaket er stoppet, eller etter 3 minutter uten trykk på klar-skjermen før opptak. Aldri under opptak (D-043).
- Teknikeren ser navn, brukernavn, showvalg og modus live, og kan avslutte en økt.

**Show-typer** ligger i `config/defaults/show_types.yaml`. Hver type peker på et forhåndsvalg av regler, brytere og layouter:

| Type | Regler | Merknad |
| --- | --- | --- |
| Podcast | Standard | Standard for 1–4 deltakere |
| Intervju | Rolig | Lengre bildelengde, færre reaksjoner |
| Panel | Standard | Fugleperspektiv brukes mer |
| Kun lyd | Motor av | Kameraer i ro; ATEM viser en fast «Kun lyd»-grafikk fra mediaspilleren, så Pearl tar opp som vanlig og filen virker i Panopto |

**Økt-objektet:**

```json
{
  "session_id": "2026-10-20T14:02:11-kanordm",
  "user": { "username": "kanordm", "display_name": "Kari Nordmann" },
  "show": { "type": "podcast", "guests": 2, "video": true, "laptop": false },
  "mode": "N3",
  "recording": { "state": "started", "started_by": "touch", "duration_s": 2472 },
  "publish": { "target": "panopto", "folder": "Mine opptak", "state": "pending" }
}
```

`started_by` er `touch`, `tech` eller `streamdeck`, så det alltid er kjent hvem som startet og stoppet.

### 7.6 Panopto (forberedt)

Publisering bygges senere, men grensesnittet og datamodellen har plass til den fra start. Pearl har innebygd Panopto-integrasjon, og REST-API-et kan opprette Panopto-opptak direkte.

- **Det Pearl kan:** opprette ad-hoc-opptak i Panopto (`POST /api/v2.0/schedule/events`), starte, stoppe, pause og forlenge dem, og åpne en kort innloggingsøkt på én time som henter en OAuth2-nøkkel på vegne av en bruker ([Pearl API](https://github.com/epiphan-video/pearl_api_swagger_ui)).
- **I grensesnittet nå:** touch-skjermen viser mål («Panopto: Mine opptak») før start, og status etter stopp («Lastes opp», «Ferdig», «Feilet»). Teknikeren ser det samme.
- **Metadata:** tittel `<show-type> – <navn> – <dato>` og forfatter = brukernavn. Companion sin Pearl-modul kan allerede sette tittel og forfatter.
- **Må avklares:** opptakene skal havne på hver brukers egen konto i Panopto. Pearl sin ad-hoc-innlogging forutsetter brukerens egen pålogging, så det må avklares hvordan et opptak opprettes på vegne av en bruker som bare har vist kortet. Se på hvordan Crestron-løsningen i de andre studioene gjør det, og bruk samme flyt.

### 7.7 ISO-opptak i ATEM

ATEM kan ta opp hver kamerainngang for seg i tillegg til programmet. CutCut styrer dette direkte fra teknikervinduet, mens Pearl fortsatt er hovedopptaker for programmet.

- **Start og stopp:** knapp i teknikervinduet (Live og Overstyring) og på Companion side 11. Motoren styrer opptaket over ATEM-protokollen (`atem-connection` har start, stopp og status for opptak), med «opptak av alle innganger» slått på i ATEM.
- **Per show-type:** `iso_record: true` i `show_types.yaml` gjør at ATEM sitt ISO-opptak starter sammen med Pearl. Av som standard.
- **Stopp:** bare av en person (`I7`). Stopper Pearl-opptaket, spør teknikervinduet om ISO-opptaket også skal stoppes.
- **Filnavn:** ATEM sitt filnavn settes til samme navn som økten (`<dato>_<show-type>_<brukernavn>`), så ISO-filene kan finnes igjen.
- **Status:** opptakstid, ledig plass og disk vises i teknikervinduet. Helsesjekk `H-ATEM-4` varsler gult under 60 minutter igjen og rødt hvis disken mangler når ISO er slått på for showet.
- **ISO-filer** brukes til reserve og etterarbeid ved behov. Publisering av dem er utenfor v1.

## 8. Skjermer

Det er tre skjermbilder fra samme server: touch-skjermen for brukeren, teknikervinduet, og oppsettsiden for første oppsett og kalibrering. Opptak kan startes og stoppes fra både touch og tekniker, og begge viser alltid samme tilstand, fordi tilstanden ligger i motoren og ikke i skjermene.

### 8.1 Brukerflyt

> **Endret etter forprosjektet (D-036):** touch-flyten har fem skjermer: hvile → klar (hvem er med, video eller kun lyd, Start) → lydsjekk 3–2–1 → opptak → ferdig. Brukeren velger ikke show-type, og deltakerne trykker ikke på navnet sitt; lydsjekken skjer automatisk under nedtellingen, og full mic-sjekk ligger i setup-hjelperen (steg 5). Fasit for utseende og flyt er `docs/design/gui-konsept.md` og `concept/touch.html`. Teksten under beskriver den opprinnelige seks-skjerms-flyten og gjelder bare der den ikke strider mot dette.

&#91;embedded content: brukerflyt · seks skjermer på touch\]

- **Kort ikke gjenkjent:** skjerm 1 viser «Kortet ble ikke gjenkjent – prøv igjen» i 5 s.
- **Kun lyd:** skjerm 4 sjekker bare lyd og Pearl; skjerm 5 viser lydnivåer i stedet for hvem som er på lufta.
- **Tekniker:** kan starte en økt på vegne av en bruker, starte og stoppe opptak, og flytte touch-skjermen til et hvilket som helst steg.
- **Hjelp-knappen:** gir et varsel med lyd i teknikervinduet og i Companion (`regi_health`).

### 8.2 Touch-skjermen (`/touch`)

Touch-skjermen er laget for en som aldri har sett systemet før. Den viser én beslutning per skjerm, i fast 16:9.

| Regel | Krav |
| --- | --- |
| Format | Fast 1920 × 1080, skaleres til skjermen; ingen rulling |
| Knapper | Minst 120 piksler høye, maks fire valg per rad, tekst minst 28 piksler |
| Farger | Bare for status: rødt = opptak eller feil, gult = advarsel, grønt = klart, blått = valgt |
| Kan ikke angres | «Avslutt opptak» krever at man holder i 1 s, med synlig fremdriftsring |
| Tekniker-tilgang | Hold logoen i 5 s og tast PIN; åpner teknikervinduet på samme skjerm |
| Kiosk | Edge i kiosk-modus; brukeren kan ikke gå ut av appen |

**Skjerm:** iiyama ProLite T2254MSC-B2AG er en 21,5″ touch-skjerm med 1920 × 1080, så touch-siden vises i full oppløsning uten skalering. Den kobles til regi-PC-en med DisplayPort eller HDMI pluss USB for touch, og Windows bruker den uten egen driver. Siden touch-siden er en vanlig nettside, kan den senere flyttes til et annet panel, for eksempel ProDVX TMP-22X (også 21,5″ med 10-punkts touch, HDMI og USB), uten endringer i appen.

&#91;embedded content: touch · Velg show, 1920 × 1080\]

&#91;embedded content: touch · Opptak, 1920 × 1080\]

| Skjerm | Viser | Knapper |
| --- | --- | --- |
| 1 Hvile | Logo, klokke, «Skann kortet ditt», diskré status | Ingen (tekniker via logo) |
| 2 Velkommen | «Velkommen, \<navn>» i 2 s | Ingen, går videre selv |
| 3 Velg show | Gjester 0–3, type, video eller kun lyd, laptop ja/nei | Neste, Avbryt |
| 4 Klar | Sjekkliste: lyd per mic, kamera, laptop, Pearl, lagring. Blir grønn selv | Start opptak (3-2-1), Tilbake |
| 5 Opptak | Tid, hvem er på lufta, deltakere, status | Avslutt (hold), Vis laptop, Hele bordet, Hjelp |
| 6 Ferdig | Lengde, «Lastes opp til Panopto» og status | Logg ut, Nytt opptak |

På skjerm 4 trykker hver deltaker på sitt navn og sier noen ord. Navnet blir grønt når riktig mic og kamera svarer. Det er hele mic- og kamerasjekken for brukeren.

### 8.3 Teknikervindu (`/tech`)

Teknikervinduet viser alt motoren vet, og lar teknikeren overstyre og konfigurere. Det kan åpnes på regi-PC-en, fra en annen PC på studionettet, eller fra touch-skjermen med PIN.

&#91;embedded content: teknikervindu · skisse, 1920 × 1080\]

| Meny | Innhold |
| --- | --- |
| Live | Økt og opptak øverst (navn, brukernavn, show, modus, opptakstid); program og preview med tilstand; multiview med overlegg; mic-stripes; neste beslutning; logg; tidslinje; start og stopp opptak |
| Overstyring | AUTO, LÅS, BIRD nå, content av/på, direkte kutt til alle kilder, preset per kamera (bare off air) |
| Brytere | Alle brytere fra 5.13, med virkning med en gang |
| Tuning | Forhåndsvalg og glidere per regel, per show-type; «lagre som standard for show-typen» |
| Show og økt | Innlogget bruker og valg; endre antall gjester eller type under økten; starte økt for en bruker; avslutte økt; flytte touch-skjermen til et steg |
| Logg | Beslutninger, live tekst, økthistorikk (hvem, når, lengde, startet fra), eksport til CSV |
| Helse | Status, responstid og siste feil per enhet og prosess; omstart av en prosess |
| Oppsett | Oppsettsiden (8.4), bare for admin |

**Tilgang:** to roller med passord. *Operatør* får Live, Overstyring, Brytere, Show og økt, Logg og Helse. *Admin* får i tillegg Tuning og Oppsett. Alle endringer logges med rolle og tidspunkt.

Toppfeltet i Live viser begge opptakene: Pearl (program) og ATEM ISO (alle kameraer), hver med egen start- og stoppknapp og tid.

### 8.4 Setup-hjelper (`/tech/setup`)

Setup-hjelperen er en veiviser på teknikersiden som tar en tekniker gjennom alt utstyret, fra tomt studio til «Klar for produksjon». Hvert steg forklarer hva som skal settes opp og hvorfor, viser hvordan, retter det selv der utstyret tillater det, og sjekker resultatet ved å lese tilbake fra utstyret.

&#91;embedded content: setup-hjelper · ti steg og hva hvert steg inneholder\]

**Slik er hvert steg bygget:**

- **Hva og hvorfor:** én setning, for eksempel «ATEM må gå i 1080p50 fordi alle kameraene gjør det».
- **Slik gjør du:** nummererte klikk-for-klikk-instrukser for utstyrets eget program eller meny, med forventet verdi i fet skrift.
- **Fiks for meg:** der API-et tillater det, setter CutCut verdien selv etter bekreftelse. Knappen finnes bare når det er trygt, og aldri under opptak.
- **Sjekk:** leser tilbake fra utstyret og viser forventet og faktisk verdi side om side.
- **Godkjent:** verdiene lagres som fasit («baseline») i `site/<studio>/baseline.yaml`. Statussiden (8.5) varsler når utstyret senere avviker fra fasiten.

Stegene og innholdet ligger i `site/<studio>/setup/*.yaml`, ikke i koden. Den samme filen brukes til veiviseren i GUI-et og til den trykte oppsettsguiden i `docs/setup/`, så de aldri kan bli ulike. Nye utstyrstyper legges til som en ny fil.

| Steg | Settes opp | Fiks for meg | Sjekk |
| --- | --- | --- | --- |
| 1 Nett og IP | Fast IP på alt utstyr etter IP-planen; studio-nett eller VLAN | – | Ping og åpen port per enhet: ATEM 9910/UDP, Companion HTTP, Pearl 443, kameraer (VISCA, XC) |
| 2 PC og Windows | Strømplan, USB-strømsparing av, aktive timer for oppdateringer, NTP, driverversjoner (NVIDIA, RØDECaster ASIO, capture-kort, TWN3) | Strømplan og USB-strømsparing via `powercfg` | Leser innstillinger og versjoner, sammenligner med `versions.yaml` |
| 3 ATEM | 1080p50, inngangsnavn (`C1`–`C4`, `BIRD`, `LAPTOP`, `C7`), HDMI ut 2 = multiview, multiview-layout og ruter, lydkilder, mediaspiller 1 og 2, disk for ISO-opptak (modell finnes automatisk) | Inngangsnavn og multiview-ruter via ATEM-protokollen (`atem-connection`) | Leser format, navn, multiview og mediaspillere |
| 4 Kameraer | **OBSBOT Tail 2:** fast IP, VISCA over IP og OSC på, NDI av, HDMI 1080p50, manuell hvitbalanse og eksponering. **Canon CR-N300:** fast IP, XC-protokoll på, egen API-bruker, HDMI/SDI 1080/50P, manuell hvitbalanse og eksponering. **Fugleperspektiv:** HDMI 1080p50, manuell hvitbalanse | Presets lagres fra veiviseren; grenser og fart settes i oppsettsiden (skisse under) | Svar fra protokollen, manuell modus, posisjon kan leses, bilde i riktig multiview-rute |
| 5 RØDECaster | Fader 1–4 = M1–M4, fader 5 = laptop, USB 1 multitrack pre-fader, hovedmiks til ATEM | – | Hver person sier noen ord: riktig spor reagerer, lekkasje til andre spor måles og lagres |
| 6 Multiview | DeckLink-kortet (D-062) får multiviewen i 1080p50 og velges på navnet; rutekart over multiviewen; forsinkelse fra ATEM til PC måles med et blinkende testbilde | Rutekartet foreslås automatisk fra bildet; hjørner kan dras | Hver rute viser riktig kilde (ATEM bytter preview gjennom kildene og videolaget sjekker) |
| 7 Companion | Import av `cutcut-pages.companionconfig` (side 10 og 11), ATEM- og Pearl-tilkobling i Companion | – (Companion har ikke API for import) | Leser `cutcut_pages_version`; trykker hver preview-knapp og leser ATEM-preview tilbake |
| 8 Makroer og grafikk | Makroer fra 7.2, «Kun lyd»-grafikk og bakgrunn i mediaspillerne | Grafikk kan lastes opp via ATEM-protokollen | Makroene finnes med riktig nummer og navn; hver kjøres og SuperSource leses tilbake |
| 9 Pearl og kort | Pearl-bruker, opptaker, inngang fra ATEM, NTP; TWN3 i COM-port-modus; kort-API-nøkkel | – | 5 s testopptak startes, stoppes og finnes; et testkort gir brukernavn |
| 10 Generalprøve | Alle deltakere sitter og snakker | – | Motoren kjører 5 min i skyggemodus; viser kutt, kuttpunkt og eventuelle avvik |

Kamerasteget har en egen side per kamera med live bilde, grenser, presets og test:

&#91;embedded content: oppsettsiden · kamera-fanen, skisse\]

**Grenser håndheves i driveren:** en kommando utenfor grensene for pan, tilt, zoom eller fart klemmes til grensen og logges. Det gjelder også kommandoer fra oppsettsiden selv.

**Regler for hjelperen:**

- Stegene kan kjøres på nytt enkeltvis, for eksempel bare «Kameraer» etter bytte av et kamera.
- «Fiks for meg» og tester som flytter kamera eller endrer ATEM er sperret mens opptak pågår.
- Alt hjelperen gjør og alle godkjenninger logges med tekniker og tidspunkt.
- Er en verdi ukjent ved første oppsett, kan teknikeren registrere den som ny fasit; endringen lagres i git med en kommentar.
- Det som ikke er kjent i dag (eksakte menynavn i nyeste fastvare, presise SuperSource-verdier) fylles inn ved første oppsett, og lagres i steg-filene.

### 8.5 Status og overvåkning (`/tech/health`)

En egen helsetjeneste i regi-core sjekker hele tiden at alt er tilkoblet, svarer og fortsatt er satt opp slik setup-hjelperen godkjente. Statussiden viser én rad per sjekk med grønt, gult eller rødt, siste verdi, siste feil og når den sist var grønn.

**Tre nivåer av sjekk:**

1. **Tilkoblet:** enheten svarer på nett og port.
2. **Fungerer:** protokollen gir fornuftige svar, for eksempel at ATEM-tilstanden kan leses eller at lyden kommer jevnt.
3. **Som avtalt:** innstillingene er de samme som i fasiten fra setup-hjelperen (`baseline.yaml`). Dette fanger at noen har endret noe, for eksempel at et kamera er satt tilbake til automatisk hvitbalanse eller at multiview-layouten er byttet.

| ID | Sjekk | Intervall | Grønt når | Avvik gir |
| --- | --- | --- | --- | --- |
| `H-NET-*` | Ping og port per enhet | 5 s | Svar under 50 ms | Rødt etter 3 feil på rad |
| `H-ATEM-1` | ATEM-tilkobling og tilstand | 1 s | Program og preview kan leses | Rødt |
| `H-ATEM-2` | Format, inngangsnavn, multiview-layout, HDMI ut 2 | 30 s | Lik fasit | Gult; rødt hvis multiview er endret |
| `H-ATEM-3` | Makroer og mediaspillere | 5 min | Alle finnes med riktig navn | Gult; layout-brytere sperres |
| `H-COMP-1` | Companion HTTP-API og `cutcut_pages_version` | 5 s | Svar under 200 ms og riktig versjon | Rødt; reservekutt via ATEM |
| `H-CAM-*` | Kamera: protokoll, posisjon, manuell modus, hvitbalanse | 10 s | Svar under 200 ms og lik fasit | Gult; kameraets vinkler tas ut ved tapt forbindelse |
| `H-AUD-1` | ASIO-strøm fra RØDECaster | 1 s | Blokker uten avbrudd | Rødt (`S4`) |
| `H-AUD-2` | Støynivå per mic i stillhet | 1 min | Under fasit + 6 dB | Gult (mic feil plassert eller støy i rommet) |
| `H-VID-1` | Capture-bilde og rutekart | 5 s | 1080p50 og rutene gjenkjennes | Gult; motoren går over til bare lyd |
| `H-PRL-1` | Pearl status, inngang, lagring, temperatur | 2–30 s | Signal, over 60 min lagring, temperatur under grensen | Rødt eller gult |
| `H-PRL-2` | Opptak kjører når det skal | 2 s | `started` under økt med opptak | Rødt med lyd |
| `H-CARD-1` | TWN3 COM-port | 10 s | Porten er åpen | Gult |
| `H-CARD-2` | Kort-API | 5 min, og ved hvert oppslag | Testoppslag under 3 s | Gult |
| `H-PROC-*` | Hjerteslag fra core, audio-capture, vision, stt, atem-bridge, touch-nettleser | 1 s | Hjerteslag hvert sekund | Gult; supervisor restarter |
| `H-PC-*` | Disk, minne, CPU, GPU-temperatur, klokke (NTP) | 30 s | Under grenser; klokkeavvik under 1 s | Gult |

I tillegg: `H-ATEM-4` sjekker ISO-disk og opptak hvert 10. sekund (gult under 60 minutter igjen, rødt hvis disken mangler når showet skal ta opp ISO), og `H-VID-2` sjekker at capture-kortet (DeckLink, D-062) leverer 1080p50 og at forsinkelsen er som målt ved oppsett.

`H-CAM-MOVE` leser posisjonen til hvert PTZ-kamera hvert 2. sekund og varsler rødt hvis et kamera har flyttet seg uten at CutCut ba om det og uten at AI-tracking er slått på for kameraet.

**Varsling:**

- **Teknikervindu:** varsellinje øverst og telling i menyen Helse; rødt varsel gir lyd.
- **Touch-skjerm:** bare det brukeren trenger: «Noe er galt med opptaket – trykk Hjelp» ved rødt på Pearl, lyd eller ATEM. Gule avvik vises ikke for brukeren.
- **Stream Deck:** `regi_health` settes til `ok`, `warn` eller `error`, og en knapp skifter farge.
- **Utenfor studio (valgfritt):** e-post eller Teams-melding til teknikere ved rødt som varer over 1 minutt. Kjøres utenfor sanntidssløyfen, så nett-trobbel aldri påvirker klippingen.
- **Morgensjekk:** ved oppstart og hver morgen kl. 07:00 kjøres hele sjekklisten, og resultatet vises på hvile-skjermen som en liten prikk (grønn eller gul) og i loggen.

**Regler for overvåkningen:**

- Et varsel går ikke av og på: det må være grønt i 30 s før det regnes som løst, og hvert varsel logges én gang med start og slutt.
- Sjekker som kan påvirke sendingen (for eksempel å trykke Companion-knapper) kjøres bare i setup-hjelperen, aldri i den løpende overvåkningen.
- `GET /api/health` gir det samme som statussiden som JSON, slik at Multimediesenteret sin egen overvåkning kan lese den.

## 9. Drift over tid

Systemet skal tåle måneder uten tilsyn: hver del kan feile og startes på nytt uten at sendingen faller ut, og alt som kan gå galt viser seg på skjermene før det merkes på lufta.

### 9.1 Når noe feiler

| Feil | Hva systemet gjør | Hva operatøren ser |
| --- | --- | --- |
| Videolaget stopper | Fortsetter på lyd alene; supervisor restarter videolaget | Gult: «Bare lyd» |
| Lyd fra RØDECaster borte over 2 s | Kutter til `BIRD`, AUTO på pause (`S4`), prøver å åpne ASIO på nytt hvert 5. sekund | Rødt: «Ingen lyd» |
| Companion svarer ikke | Kutter direkte på ATEM (`S5`); layouter stoppes | Gult: «Reservekutt» |
| ATEM utilgjengelig | Ingen kutt; ATEM står på siste bilde | Rødt: «ATEM» |
| Et kamera faller ut av nett | Kameraets vinkler tas ut av utvalget; videoen går fortsatt via HDMI/SDI | Gult på kameraet |
| Pearl svarer ikke eller opptak stopper | Varsler med lyd; prøver ikke å starte på nytt selv (`I7`) | Rødt: «Opptak» |
| regi-core krasjer | Supervisor restarter innen 5 s med samme oppsett og økt; ATEM og Pearl påvirkes ikke | Kort «Starter på nytt» |
| PC-en går ned | ATEM står på siste bilde, Pearl tar opp videre; operatør bruker Stream Deck | Skjermene borte |
| Touch-nettleseren henger | Supervisor sjekker at siden svarer og starter Edge kiosk på nytt; økten ligger i motoren og er uendret | Touch blinker kort |
| Kortleser frakoblet | Touch viser «Kortleser mangler – trykk Hjelp»; tekniker kan starte økt manuelt | Gult: «Kortleser» |
| Kort-API svarer ikke | «Kortet kunne ikke sjekkes nå»; tekniker kan godkjenne «Start uten innlogging» | Gult: «Kort-API» |

### 9.2 Oppsett av Windows-maskinen

- [ ] Egen PC kun for regi, lokal bruker som logger inn automatisk, ingen annen programvare
- [ ] Windows Update: aktive timer satt utenfor sendetid; oppdateringer installeres manuelt i servicevindu
- [ ] Strøm: høy ytelse, aldri hvilemodus, skjermsparer av, USB-strømsparing av
- [ ] Nett: fast IP, studio-nett uten internett-krav under sending; NTP-tid
- [ ] Tjenester: supervisor og Companion starter ved oppstart; touch og tekniker åpnes i Edge kiosk-modus
- [ ] Driverversjoner (NVIDIA, RØDECaster ASIO, capture-kort) låst og notert i `site/<studio>/equipment/versions.yaml`
- [ ] UPS med automatisk, ryddig nedstenging ved lang strømstans

### 9.3 Vedlikehold

| Hva | Hvordan | Når |
| --- | --- | --- |
| Oppsett og konfig | Kode og studio-oppsett (`site/<studio>/`) ligger i hver sitt git-repo; hver lagring fra skjermene er en commit i studio-repoet | Automatisk |
| Utstyrsoppsett | Eksport av ATEM `.xml`, Companion-eksport og kamera-presets | Etter hver endring |
| Logger | JSON-linjer, roteres daglig, beholdes 30 dager | Automatisk |
| Firmware | Låst i produksjon; nye versjoner testes med simulator og én prøvesending | Servicevindu |
| Morgensjekk | Automatisk test ved oppstart: alle enheter svarer, ASIO åpner, multiview har bilde, Pearl har lagring | Hver oppstart |
| Helsestatus | `GET /api/health` svarer med status per del, kan leses av ekstern overvåkning | Hele tiden |

## 10. App-API, testing og akseptansekriterier

Skjermene, Companion og eventuell ekstern overvåkning bruker samme API. Alle endringer som påvirker sendingen logges med hvem som gjorde dem.

### 10.1 REST (`http://10.10.10.40:8080/api`)

| Metode og sti | Gjør |
| --- | --- |
| `GET /health` | Status per del: lyd, video, Companion, ATEM, hvert kamera, Pearl, kortleser, kort-API |
| `GET /state` | Hele nåtilstanden: økt, modus, bilde på lufta, preview og tilstand, mic-er, content, opptak |
| `GET /session` | Aktiv økt (seksjon 7.5), eller ingen |
| `POST /session` `{"username": "kanordm"}` | Tekniker starter økt for en bruker uten kort |
| `PUT /session/show` `{"guests": 2, "video": true, "type": "podcast"}` | Lagre showvalg; setter modus og regler. `type` er valgfri og hentes fra studio-oppsettet når touch ikke sender den (D-036); laptop oppdages fra multiview |
| `DELETE /session` | Logg ut (avvises under opptak) |
| `POST /touch/step` `{"step": "countdown"}` | Flytt touch-skjermen til et steg: `idle`, `ready`, `countdown`, `rec`, `done` (bare tekniker, D-036) |
| `POST /touch/again` | «Ta et nytt opptak» på ferdig-skjermen: tilbake til klar med samme bruker og valg, ny økt (touch) |
| `POST /help` | Hjelp-knappen: varsel til tekniker |
| `POST /recording` `{"action": "start"}` | Start eller stopp Pearl-opptak; `started_by` settes fra hvem som kaller |
| `POST /auto` `{"on": true}` | AUTO på eller av |
| `POST /lock` `{"on": true}` | LÅS gjeldende bilde |
| `POST /cut` `{"shot": "BIRD"}` | Manuelt kutt direkte til program |
| `POST /preview` `{"shot": "CU:P2"}` | Legg et bilde på preview; motoren tar det på neste kuttpunkt |
| `POST /features` `{"reactions": true}` | Slå brytere av eller på (5.13) |
| `POST /content` `{"enabled": false}` | Slå content av eller på |
| `POST /preset` `{"preset": "rolig"}` | Bytt forhåndsvalg (Rolig, Standard, Energisk) |
| `POST /rules/overrides` `{"T2_confirm_ms": 1000}` | Finjuster enkeltverdier oppå forhåndsvalget; `null` nullstiller. Gjelder fra neste tikk og overlever omstart (admin, ADR-0011) |
| `GET /shows`, `GET /shows/{id}`, `PUT /shows/{id}` | Les og lagre show-oppsett (validert) |
| `GET /settings/devices`, `PUT /settings/devices`, `GET /settings/devices.yaml` | Utstyrsadresser (IP, Companion): les, endre (admin, `null` nullstiller), last ned som `devices.yaml` (D-055) |
| `GET /setup/multiview`, `POST /setup/multiview/check` | Rutekart, det ATEM viser, anbefalt oppsett og avvik (`H-MV-*`, D-055); `check` sjekker på nytt og varsler (D-056) |
| `POST /setup/mic-test/{P}` | Start mic-test for en deltaker |
| `POST /setup/color-match` | Kjør fargematching mot referansekamera |
| `POST /setup/cameras/{C}/calibrate` | Kjør kameraet gjennom området innenfor grensene og mål fart |
| `POST /cameras/{C}/preset/{n}` | Hent preset (bare når kameraet er av program og preview) |
| `GET /log?since=…` | Beslutningslogg, med live tekst hvis bryteren er på |
| `GET /log.csv`, `GET /sessions?days=…`, `GET /sessions.csv` | Logg og økthistorikk (hvem, når, lengde, startet fra) som tabell og CSV |
| `GET /debug-package` | Feilsøkingspakke (logg, konfig, versjon, helse) som zip, uten hemmeligheter (admin, 12.1) |

Kortnummeret finnes ikke i API-et: kortleseren er koblet direkte til motoren, så UID aldri sendes over nettet (`I8`). Touch-skjermen er innlogget som rolle `touch` og kan bare kalle det brukeren skal kunne gjøre.

**Setup-hjelper og helse (rolle `admin`):**

| Metode og sti | Gjør |
| --- | --- |
| `GET /setup/steps` | Alle steg med status (ikke startet, feil, godkjent) |
| `POST /setup/steps/{id}/check` | Kjør sjekken for et steg og få forventet og faktisk verdi |
| `POST /setup/steps/{id}/fix` | «Fiks for meg», bare der steget støtter det og aldri under opptak |
| `POST /setup/steps/{id}/approve` | Godkjenn og lagre som fasit i `baseline.yaml` |
| `GET /health/checks` | Hele sjekkatalogen fra 8.5 med siste resultat og historikk |
| `POST /health/checks/{id}/run` | Kjør en sjekk nå |

ISO-opptak (rolle `operator`): `POST /iso-recording` `{"action": "start"}` eller `stop`, og `GET /iso-recording` for status, opptakstid og ledig plass.

AI-tracking (rolle `operator`): `POST /cameras/{C}/ai-tracking` `{"on": true}` slår tracking av eller på for ett kamera etter reglene `AT1`–`AT6`.

### 10.2 WebSocket (`/ws`)

Serveren sender meldinger med `type`: `state` (hele tilstanden, ved tilkobling), `meters` (mic-nivåer, 20 per sekund), `decision` (objektet i 5.8), `vision` (overlegg, 5 per sekund), `health` (ved endring) og `alert` (varsel med nivå og tekst), session (økt og showvalg ved endring) og touch (hvilket steg touch-skjermen står på). Klienten sender bare kommandoer som også finnes i REST.

### 10.3 Testing

- **Simulator:** `sim/` lager syntetiske mic-signaler, munnbevegelse og content-hendelser, som prototypen gjør. Hele motoren kan kjøres uten utstyr.
- **Avspilling:** ekte sendinger tas opp som mic-spor + beslutningslogg. Ny kode kjøres mot de samme sporene, og avvik i kutt rapporteres.
- **Enhetstester per regel:** hver regel-ID har minst én test som viser at den slår til og én som viser at den ikke gjør det.
- **Falske enheter:** testserver for Companion, Pearl og kameraer som svarer som de ekte, inkludert tidsavbrudd og feil.

### 10.4 Akseptansekriterier for v1

- [ ] Kutt kommer innen 150 ms etter at bekreftelsestiden er nådd (målt fra lyd inn til Companion-kall).
- [ ] På tre testsendinger: færre enn 2 kutt per 10 minutter som operatøren ville gjort annerledes, vurdert i etterkant fra opptak og beslutningslogg (D-049; skyggemodus var opprinnelig kravet).
- [ ] Ingen kutt til et kamera som beveger seg, eller til tomt bilde, i 10 timers test.
- [ ] Lekkasje: med én person som snakker høyt, ingen kutt til andre deltakere i 10 minutters test.
- [ ] Content: ny slide vises innen 1 s; laptop koblet fra fjernes fra utvalget innen 1 s.
- [ ] Alle moduser `N1`–`N4C` testet med riktig utvalg og reservebilder.
- [ ] Videolaget kan drepes under sending uten at kuttingen stopper.
- [ ] regi-core kan drepes og er tilbake innen 5 s med samme oppsett.
- [ ] Pearl-status på touch-skjermen stemmer med Pearl sitt eget grensesnitt, og stopp uten trykk varsles innen 5 s.
- [ ] 72 timers kontinuerlig drift uten minnelekkasje eller tapte tilkoblinger.

* [ ] Minst 90 % av taler-kuttene tas på kuttpunkt `K1` eller `K2`, ikke ved maks ventetid `K3` (målt på opptatte sendinger).
* [ ] Preview viser neste bilde minst 300 ms før det tas til program i 95 % av taler-kuttene.
* [ ] Ingen kutt tilbake til forrige bilde innen 4 s (`H2`) i 10 timers test.
* [ ] Med alle brytere av gir grunnmodus samme resultat som med bryterne på og videolaget stoppet.

- [ ] Fra kortet skannes til «Velkommen, \<navn>» vises: under 2 s når kort-API svarer normalt.
- [ ] Opptak startet fra touch vises i teknikervinduet innen 1 s, og omvendt; stopp fra én side kan aldri «vinnes» av den andre.
- [ ] Kun lyd: opptaket i Pearl har lyd og «Kun lyd»-grafikk, og ingen kamera beveger seg.
- [ ] Kortnummer finnes ikke i logger, database eller API (automatisk test søker etter testkortets UID).
- [ ] Fem førstegangsbrukere fullfører fra kort til ferdig opptak uten hjelp.
- [ ] Oppsettsiden: alle enheter grønne, og en kommando utenfor kameragrensene blir klemt og logget.

## 11. Byggerekkefølge for AI-utvikling

Bygg i denne rekkefølgen, og la hvert steg være ferdig med tester før neste starter. Hvert steg er en avgrenset oppgave en AI-utvikler kan få med denne fanen som spesifikasjon.

1. **Planer:** agenten skriver implementasjonsplaner for alle moduler etter malen i 0.4. Ferdig når et menneske har godkjent dem.
2. **Kjerne uten utstyr:** Pydantic-modeller (oppsett, økt, beslutning, meldinger), regimotor med grunnmodus: `T`-, `S`-, `P`-, `K`- og `H`-regler, roller, preview-tilstander og simulator. Ferdig når alle regeltester går grønt.
3. **Skjermer mot simulator:** touch-flyten (fem skjermer, D-036, etter `concept/`), teknikervinduet med menyer og oppsettsiden, alle mot simulert motor. Ferdig når touch-flyten kan gjennomføres med Playwright-test.
4. **Lyd inn:** ASIO fra RØDECaster, Silero VAD, dominans, lekkasjematrise, frasegrenser. Ferdig når lydsjekken under nedtellingen på touch og mic-sjekken i setup-hjelperen (steg 5) virker.
5. **Companion og ATEM:** knappekart side 10–11, preview og take, custom variables, ATEM-leser, makrosjekk. Ferdig når motoren klipper via preview.
6. **Pearl og økter:** opptaksstatus, start og stopp fra begge sider, kortleser og kortoppslag, show-typer, kun lyd. Ferdig når hele flyten fra kort til ferdig opptak virker.
7. **Fugleperspektiv og content:** `B`- og `CT`-regler med content-deteksjon. Ferdig når alle moduser `N1`–`N4C` er testet.
8. **Kameradrivere og oppsett:** `obsbot` og `canon_xc` med presets, grenser, kalibrering og hvitbalanse. Ferdig når grensene håndheves i driveren. Setup-hjelperen (8.4) og statussiden (8.5) bygges i samme steg, ett utstyr av gangen.
9. **Drift:** supervisor, tjenester, kiosk, morgensjekk, helse-API, 72 timers test. Her er grunnmodus klar for produksjon.
10. **Brytere, i denne rekkefølgen:** `video_confirm`, `framing_variety`, `reactions`, `slow_zoom`, `layouts`, `live_transcript`, `turn_prediction`. Hver testes alene i studio før den slås på; i skyggemodus når studioet er i drift (D-049).
11. **Fargematching og Panopto:** gråkort-måling og off-air-justering; publisering til Panopto når eierskapet er avklart.

**Åpne spørsmål før bygging:**

- Hvilket kamera brukes som fugleperspektiv, og har det IP-styring?
- Står laptopen alltid på inngang 6, eller kan det komme flere content-kilder?
- kort-API: tjenestenøkkel, svarformat, og om kortnummeret skal sendes som hex i normal eller omvendt byte-rekkefølge (sjekk mot Crestron-oppsettet).
- Panopto: hvordan opprettes opptaket på brukerens egen konto når brukeren bare har vist kortet?
- Montering og kabler for touch-skjermen: avstanden til PC-en avgjør om det trengs forlenger for skjermsignal og USB.
- ATEM-modell: støtter `atem-connection` og Companion ATEM Mini Extreme ISO G2 fullt ut (tilstand, makroer, SuperSource, opptak)? Hvis ja: G2; hvis ikke: Extreme ISO.
- OBSBOT AI-tracking: virker OSC SetAiEnable på deres fastvare, og hvor rolig blir tracking med fart «lat»?
- Hvor lenge skal opptak ligge på Pearl og ATEM-disken før de slettes lokalt?

## 12. Utviklingsgrunnlag

Prosjektet skal kunne tas over av et menneske eller en AI-agent når som helst, uten muntlig overlevering. Derfor ligger all kunnskap i repoet, ved siden av koden den beskriver, og alt som kan genereres fra koden genereres.

### 12.1 Dokumentasjon for AI og menneske

| Fil eller mappe | Innhold | Holdes oppdatert slik |
| --- | --- | --- |
| `README.md` | Hva CutCut Studio er, hvordan man starter det lokalt med simulatoren på under 10 minutter | Sjekkes i CI: kommandoene i README kjøres |
| `AGENTS.md` | Regler for AI-agenter: kommandoer for test og bygg, kodestil, ufravikelige regler (0.2), hva som aldri skal endres uten menneske | Endres bare via pull request med menneskelig godkjenning |
| `docs/STATUS.md` | «Hvor er vi nå»: hva som er ferdig, hva som pågår, kjente feil, neste steg | Oppdateres på slutten av hver arbeidsøkt, av menneske eller agent |
| `docs/spec/` | Denne spesifikasjonen eksportert til Markdown, med versjon og dato | Ny eksport når spesifikasjonen endres |
| `docs/adr/NNNN-tittel.md` | Én fil per arkitekturbeslutning: kontekst, beslutning, konsekvens, status | Ny fil for hver ny beslutning; gamle erstattes, aldri slettes |
| `docs/plans/` | Implementasjonsplanene fra 0.4 | Oppdateres når planen endres |
| `docs/runbooks/` | Feilsøking per symptom: «Ingen lyd», «Kamera beveger seg ikke», «Opptak startet ikke» – med hva man sjekker i hvilken rekkefølge | Ny runbook etter hver hendelse som tok over 10 minutter å løse |
| `docs/setup/` | Oppsettsguide, generert fra setup-hjelperens steg-filer | Genereres i CI |
| `docs/architecture/` | Tegninger som Mermaid i Markdown (kan versjoneres og leses av AI) | Endres sammen med koden |
| `docs/reference/` | API (OpenAPI fra FastAPI), konfigskjema (JSON Schema fra Pydantic), regeltabell | Genereres i CI; bygg feiler hvis generert fil avviker |
| `CHANGELOG.md` | Endringer per versjon, etter *Keep a Changelog* | Fra commit-meldinger ved hver release |
| `src/cutcut/<modul>/README.md` | Ansvar, inn- og utdata, regel-ID-er modulen eier, akseptansekriterier | Endres sammen med modulen |

**Sporbarhet:** hver regel-ID (for eksempel `T2`, `K1`) finnes som konstant i koden, som navn på testen som prøver den, og i loggen. Et skript lager `docs/reference/traceability.md` som viser regel → kode → test, og CI feiler hvis en regel mangler test.

**For feilsøking:** hver logglinje har tid, prosess, modul, regel- eller sjekk-ID og en `correlation_id` som følger en beslutning fra lyd inn til kommando ut. Teknikervinduets logg kan eksporteres som en pakke (logg, konfig, versjon, helsestatus) som kan gis til et menneske eller en AI for analyse.

### 12.2 Repo og filstruktur

Kode og studio-oppsett holdes adskilt. Koden er lik for alle studioer; alt som er spesielt for ett studio ligger under `site/<studio>/`. Da kan et nytt studio settes opp uten kodeendring.

```text
CutCutStudio/
  README.md  AGENTS.md  CHANGELOG.md  LICENSE
  pyproject.toml  uv.lock          # Python, låste versjoner
  package.json  pnpm-lock.yaml     # UI-arbeidsområde
  docs/  (se 12.1)
  src/cutcut/
    core/        # regimotor, moduser, regler, tilstand, beslutninger
    audio/       # VAD, dominans, frasegrenser (i core); capture/ = egen prosess audio-capture (ADR-0014)
    vision/      # capture, ruter, ansikt og munn, content, farge (egen prosess)
    stt/         # live tekst (egen prosess, bryter)
    session/     # TWN3-kortleser, kortoppslag, økter, show-typer
    devices/     # companion, atem (klient mot atem-bridge), pearl, cameras/{base,obsbot,canon_xc}
    health/      # sjekkatalog, fasit-sammenligning, varsler
    setup/       # setup-hjelperens motor (leser steg-filer)
    api/         # FastAPI, REST og WebSocket, roller
    supervisor/  # prosesser, hjerteslag, omstart, kiosk-vakt
    common/      # modeller (Pydantic), klokke, logging, konfig
  ui/
    packages/design/   # felles design-tokens og komponenter
    packages/client/   # felles WebSocket-klient og typer (generert fra OpenAPI)
    apps/touch/        # brukerens touch-skjerm, fast 1920×1080
    apps/tech/         # teknikervindu, setup-hjelper, status
  config/
    schema/            # generert JSON Schema
    defaults/          # standardverdier, regelpresets, show-typer
  site/
    example/           # eksempelstudio for simulator og tester
  sim/                 # simulator, scenarioer og avspilling
  bridges/atem/        # atem-bridge: Node.js + atem-connection (ADR-0012)
  concept/             # GUI-konsept fra forprosjektet (Vercel), erstattes av ui/apps/simulator i M1
  tests/  unit/  rules/  integration/  e2e/
  tools/               # skript: generer dokumentasjon, sjekk sporbarhet, lag pakke
  installer/           # Windows-installasjon og tjenestedefinisjoner
```

Studio-oppsettet for hvert studio ligger i et eget, lite git-repo (`cutcut-site-<studio>`) med `devices.yaml`, `shows/`, `setup/`, `baseline.yaml` og `equipment/` (ATEM-oppsett, Companion-eksport, kamera-presets). Hemmeligheter ligger aldri i noen av repoene.

**På regi-PC-en:**

```text
C:\CutCut\
  versions\1.4.2\  versions\1.5.0\   # installerte versjoner, hver med egen Python og UI
  current  → versions\1.5.0\         # katalog-lenke; supervisor starter alltid denne
  site\                              # klone av studio-repoet
  data\  cutcut.db  logs\  exports\  # kjøredata og logger
  models\                            # modeller med sjekksum, delt mellom versjoner
```

### 12.3 Versjonering og utrulling

- **Git-flyt:** én hovedgren (`main`) som alltid kan rulles ut; korte grener per endring; pull request med grønn CI og minst ett menneskelig blikk. AI-agenter jobber på egne grener og merger aldri selv.
- **Commit-meldinger:** *Conventional Commits* (`feat(core): ...`, `fix(devices/canon): ...`), som gir changelog automatisk.
- **Versjonsnummer:** *SemVer*. Hovedversjon økes når konfigformatet eller API-et endres på en måte som krever migrering.
- **Konfig har egen skjemaversjon** (`schema_version`). Nye versjoner har migreringsskript som oppgraderer gamle filer, og CutCut starter ikke med en konfig den ikke forstår.
- **CI per pull request:** typesjekk, linting, enhetstester, regeltester, simulator-test av hele flyten, Playwright-test av touch-skjermene, generert dokumentasjon uten avvik, sårbarhetssjekk av avhengigheter.
- **Release:** et tag lager en ferdig Windows-pakke med Python, avhengigheter og bygget UI, pluss sjekksum og programvareliste (SBOM).
- **Utrulling:** bare i servicevindu. Ny versjon pakkes ut ved siden av den gamle, `current` byttes, og supervisor kjører morgensjekken. Feiler den, byttes `current` automatisk tilbake. De tre siste versjonene beholdes.
- **Modeller** versjoneres i en manifestfil med navn, versjon og sjekksum, og lastes ned ved installasjon; de ligger ikke i git.

### 12.4 Sikkerhet og personvern

| Område | Tiltak |
| --- | --- |
| Nett | Studioutstyret på eget VLAN. Regi-PC-en når bare kort-API, Panopto og oppdateringer ut av nettet (brannmur med tillatelsesliste). Windows-brannmuren slipper bare inn port 8080 fra studionettet |
| Tilgang til appen | Roller: `touch` (bare fra PC-en selv), `operator` og `admin`. Teknikere logger inn med eget ansattkort på touch (hold logoen) eller med brukernavn i teknikervinduet, og må stå på en liste over godkjente teknikere i studio-oppsettet. PIN som reserve |
| Økter | Informasjonskapsel som er `HttpOnly` og `SameSite=Strict`; utløper etter 8 timer; logg ut ved inaktivitet i teknikervinduet |
| Kryptering | Touch går mot `localhost`. Teknikervinduet fra andre maskiner går over HTTPS med sertifikat fra IT-avdelingen |
| Hemmeligheter | Kort-API-nøkkel, Pearl- og kamerapassord i Windows Credential Manager (via `keyring`), aldri i git eller logg |
| Windows | Egen lokal bruker for kiosk med tilordnet tilgang (bare Edge med touch-siden); tjenestene kjører som en egen tjenestekonto uten administratorrett; BitLocker på; USB-lagring av for kiosk-brukeren |
| Utstyr | Egne brukere med minst mulig rettigheter på Pearl og Canon; standardpassord byttes i setup-hjelperen |
| Kortnummer | Leses, slås opp og glemmes (`I8`). En test i CI søker etter testkortets nummer i logg, database og API-svar |
| Personopplysninger | Brukernavn og økthistorikk beholdes 90 dager; live tekst lagres ikke som standard. Begge avklares med Multimediesenteret sitt personvernombud |
| Avhengigheter | Låste versjoner, månedlig sårbarhetssjekk, oppdatering i servicevindu |
| Revisjonslogg | Alle endringer av oppsett, brytere, overstyringer og innlogginger logges med hvem og når |

### 12.5 GUI-grunnmur

- **Én kilde til sannhet:** all tilstand ligger i motoren. Skjermene får et fullt øyeblikksbilde når de kobler til og endringer over WebSocket etterpå. To skjermer kan derfor aldri vise forskjellig status.
- **Ingen optimistiske knapper for viktige handlinger:** «Start opptak» og «Avslutt» viser «Starter…» til Pearl bekrefter, og feil vises i klartekst.
- **Tilkobling borte:** skjermen blir aldri blank. Den viser siste kjente tilstand grået ut med «Kobler til igjen» og prøver på nytt automatisk.
- **Felles designsystem** i `ui/packages/design`: farger som tokens med fast betydning (rødt = program og opptak, grønt = preview og klart, gult = venter og advarsel, blått = valgt og content), én typografi, komponenter for knapper, mic-stripe, statusrad og varsel.
- **Touch:** fast 1920 × 1080-flate som skaleres til skjermen; knapper minst 120 piksler; ingen avhengighet av hover; tydelig trykk-respons; norsk tekst i egen språkfil.
- **Tekniker:** skrivebordsoppsett med tastatursnarveier (mellomrom = AUTO, B = fugleperspektiv), målere tegnet på canvas i 20 bilder/s for å spare ytelse.
- **Testing:** hvert touch-steg har et skjermbilde-test i Playwright, så en endring som flytter en knapp blir oppdaget.
- **Typer fra API-et:** TypeScript-typene genereres fra OpenAPI, så grensesnitt og motor ikke kan bli uenige om et felt.

## 13. Overlevering til AI-agent

Spesifikasjonen er nok til at en agent kan starte med kjernen, simulatoren og skjermene. Det som mangler, er ekte data fra studioet og noen beslutninger som bare Multimediesenteret kan ta. Uten ekte lydspor og en menneskelig klippeliste kan reglene bare tunes mot simulatoren, så det er det viktigste å skaffe.

### 13.1 Startinnhold i repoet

Repoet er `github.com/multimediesenteret/CutCutStudio`. Ved overlevering skal det inneholde:

| Fil eller mappe | Innhold |
| --- | --- |
| `README.md` | Hva prosjektet er, status, hvor spesifikasjonen ligger |
| `AGENTS.md` | Regler for AI-agenter: første oppgave, ufravikelige regler, arbeidsflyt, hva som krever menneske |
| `docs/spec/` | Denne spesifikasjonen, Teknisk referanse og Evaluering som Markdown og PDF, med dato |
| `docs/STATUS.md` | Startstatus: «ingen kode, planer ikke laget» |
| `docs/open-questions.md` | Tabellen i 13.2, holdes oppdatert |
| `docs/adr/` | Arkitekturbeslutningene fra 0.3 som egne filer |
| `docs/prototype/` | Den klikkbare prototypen som referanse for oppførsel og regel-ID-er |
| `site/multimediesenteret/equipment/obsbot/` | OBSBOT OSC-definisjonen og VISCA-tabellen |
| `.github/` | Mal for pull request og issue, CODEOWNERS |

### 13.2 Det som mangler, og hvem som skaffer det

| # | Mangler | Trengs til | Ansvar | Blokkerer |
| --- | --- | --- | --- | --- |
| 1 | **Opptak fra ekte sendinger:** 3–5 episoder med hvert mic-spor som WAV (fra RØDECaster multitrack), multiview som video (capture-kortet), og ATEM ISO-filer | Tuning av lydreglene, tester med avspilling, videolaget | Multimediesenteret | Steg 4 og 7 |
| 2 | **Menneskelig klippeliste** for de samme opptakene: tidspunkt og kilde for hvert kutt, laget av en erfaren klipper | Fasit for «feilkutt per 10 minutter» (10.4) | Multimediesenteret | Akseptanse |
| 3 | **Studiotegning og bilder:** bordplan, kameraplassering, lys, bilder av hvert kamerautsnitt | Rutekart, presets, utsnittsregler | Multimediesenteret | Steg 6–8 |
| 4 | **Kort-API:** nøkkel, svarformat, eksempel på svar, kortformat (hex og byte-rekkefølge fra Crestron) | Kortinnlogging | Multimediesenteret IT | Steg 6 |
| 5 | **Panopto:** hvordan opptak legges på brukerens konto uten passord (som i Crestron-studioene) | Publisering | Multimediesenteret og Panopto-admin | Senere |
| 6 | **Canon XC-kommandoliste** fra Canon | Canon-driver | Multimediesenteret via Canon | Steg 8 |
| 7 | **ATEM-modell** og bekreftet støtte i `atem-connection` og Companion | Integrasjon | Multimediesenteret | Steg 5 |
| 8 | **Regi-PC og Windows:** er PC-en sentralt administrert (Intune/gruppepolicy)? Kan kiosk, tjenester, strømplan og oppdateringstider settes lokalt? | Drift (9) | Multimediesenteret IT | Steg 9 |
| 9 | **Nett:** VLAN, IP-plan bekreftet, brannmur ut mot kort-API og Panopto | Alt | Multimediesenteret IT | Steg 5 |
| 10 | **Personvern:** behandlingsgrunnlag og lagringstid for brukernavn, økthistorikk og eventuell live tekst | Lagring og logg | Multimediesenteret personvernombud | Før produksjon |
| 11 | **Lisens for repoet** og hvem som eier koden | Avhengigheter og deling | Multimediesenteret | Steg 1 |
| 12 | **Kontaktpersoner:** produkteier, tekniker for test i studio, IT-kontakt | Godkjenning av planer og tester | Multimediesenteret | Steg 1 |

### 13.3 Agenten har ikke tilgang til studioutstyret

Agenten jobber i et skymiljø uten tilgang til ATEM, kameraer eller RØDECaster. Derfor:

- Alt bygges og testes først mot simulatoren og falske enheter (`sim/`, `tests/integration/`).
- Hver integrasjon får et **maskintestskript** (`tools/hw-test/<enhet>.py`) som en tekniker kjører i studio. Skriptet skriver en rapport (JSON og Markdown) som legges i en pull request eller et issue, så agenten kan lese resultatet.
- Opptakene fra 13.2 brukes som «maskinvare på bånd»: motoren kjøres mot dem i CI.
- Ekte kommandoer mot utstyr kjøres bare når et menneske starter dem.

### 13.4 Beslutning som må tas før koding: ATEM-biblioteket

`atem-connection` (Node.js) er det mest brukte og best vedlikeholdte biblioteket for ATEM, og brukes av Companion. Python-alternativet er mindre brukt. Anbefaling (`ADR-12`): en liten egen prosess, `atem-bridge`, skrevet i Node.js med `atem-connection`, som snakker med regi-core over den samme interne meldingsbussen. Resten av systemet forblir Python. Agenten skal bekrefte dette i implementasjonsplanen for ATEM.

### 13.5 Milepæler for første versjon

| Milepæl | Innhold | Ferdig når |
| --- | --- | --- |
| M0 Planer | Implementasjonsplaner for alle moduler; issues og milepæler i GitHub | Planene er godkjent av produkteier |
| M1 Simulator | Kjerne med grunnmodus, simulator, API, teknikervindu og touch mot simulator | Hele brukerflyten og alle regeltester virker uten utstyr |
| M2 Studiotest | Lyd inn, ATEM-lesing, Companion, Pearl-status, supervisor | Motoren klipper live i studio via preview; testsendinger vurderes av operatør (D-049: ingen skyggerunde mens studioet ikke er i bruk) |
| M3 Grunnmodus i drift | Klipping via preview, kortinnlogging, kameradrivere, setup-hjelper og helse | Akseptansekriteriene i 10.4 for grunnmodus er oppfylt |
| M4 Brytere | Videolag, reaksjoner, utsnitt, layouter, AI-tracking, live tekst | Hver bryter testet alene i studio; i skyggemodus når studioet er i drift (D-049) |

### 13.6 Første oppgave til agenten

> Les `AGENTS.md`, hele `docs/spec/` og `docs/open-questions.md`. Lag implementasjonsplaner i `docs/plans/` etter malen i 0.4 for alle moduler i rekkefølgen fra seksjon 11, og et forslag til GitHub-issues og milepæler M0–M4. Skriv ingen produksjonskode før planene er godkjent. Oppdater `docs/STATUS.md` når du er ferdig, og list spørsmål du trenger svar på.

## Kilder

- [Epiphan Pearl REST-API v2.0 (OpenAPI)](https://github.com/epiphan-video/pearl_api_swagger_ui) · [Epiphan: REST-API i firmware 4.24.1](https://www.epiphan.com/product-news/new-firmware-update-control-system-updates-rest-api-usb-button-led-light-support-and-easy-file-sharing/) · [Companion-modul for Epiphan Pearl](https://github.com/bitfocus/companion-module-epiphan-pearl)
- [Companion HTTP Remote Control](https://companion.free/user-guide/v4.2/remote-control/http-remote-control) · [Companion ATEM-modul](https://github.com/bitfocus/companion-module-bmd-atem)
- [ATEM Mini-serien sammenlignet](https://www.syntex.cz/media/ant/Syntex_Blackmagic_Design_ATEM_Mini_vs_Pro_vs_Extreme_EN_2_2021.pdf)
- [OBSBOT VISCA-guide](https://www.obsbot.com/explore/obsbot-tail-air/visca-over-ip) · [OBSBOT OSC](https://www.obsbot.com/webcam/osc) · [Canon CR-N300 datablad](https://www.fullcompass.com/common/files/60067-CRN300DataSheet.pdf)
- [RØDECaster Virtual Devices og ASIO](https://help.rode.com/hc/en-us/articles/11891033629839-What-is-the-Virtual-Devices-Driver-for-the-R%C3%98DECaster-Pro-II-Duo) · [Silero VAD](https://pypi.org/project/silero-vad) · [Light-ASD](https://ar5iv.labs.arxiv.org/html/2303.04439)
