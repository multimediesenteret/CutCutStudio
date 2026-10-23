# Teknisk referanse

Oppdatert Oct 20, 2026. Protokoller, kommandoer og kilder for alt utstyret, samlet så ingen trenger å lete eller lime inn på nytt. Spesifikasjonen gjelder ved uenighet; denne fanen er oppslagsverket.

## Valgt teknikk per enhet

I drift brukes én protokoll per enhet: den som snakker direkte med enheten, er dokumentert av produsenten, og ikke krever et ekstra program i mellom. Alt annet er reserve eller oppsett.

| Enhet | I drift | Reserve eller bare oppsett | Hvorfor |
| --- | --- | --- | --- |
| ATEM Mini Extreme ISO (G2) | Lesing: ATEM-protokollen via `atem-connection` (UDP 9910). Kutt og layouter: via Companion | Direkte kutt via `atem-connection` hvis Companion faller ut | Companion og Stream Deck bruker de samme knappene; motoren ser alltid sannheten fra ATEM |
| Companion | HTTP remote control (`/api/location/…`, `/api/custom-variable/…`, `/api/connections`) | REST API v2 og Prometheus-metrikk for helse | HTTP-API-et har vist seg stabilt over flere hovedversjoner |
| OBSBOT Tail 2 | VISCA over IP direkte til kameraet (UDP 52381) | OSC direkte til kameraet (UDP 57110/57120) for fargetemperatur og eksponering; OBSBOT Center brukes ikke | VISCA er en bransjestandard uten mellomledd; OBSBOT Center er en skrivebordsapp som måtte vært i gang |
| Canon CR-N300 | XC-protokollen (HTTP) | VISCA over IP | XC gir farge og eksponering med direkte verdier |
| Epiphan Pearl Nexus | REST API v2.0 (HTTPS, Basic-autentisering) | Companion sin Pearl-modul for knapper | Offisielt API med status for opptak, innganger og lagring |
| RØDECaster Pro II | ASIO, USB 1 multitrack | – | Rene spor med lav forsinkelse |
| INOGENI 4KXUSB3 | UVC, YUY2 1080p50 | ATEM-ens webkamera-utgang (USB-C) med Multi View valgt (D-071) | Standard webkamera i Windows, ingen driver |
| ELATEC TWN3 | Virtuell COM-port | – | Uavhengig av tastaturfokus |
| Kort-API | HTTPS med tjenestenøkkel | Tekniker kan starte økt uten kort | Bare ved innlogging, aldri i sanntid |

**Regel:** når en ny enhet legges til, velges protokoll etter samme tre krav: direkte til enheten, dokumentert av produsenten, og mulig å lese tilbake tilstand.

## Companion

**Versjon:** siste stabile 5.x, låst i produksjon. Brukerveiledningen for 5.1 og beta ligger på companion.free; siste stabile utgave på GitHub var 5.0.2 da dette ble skrevet. Companion kjører på regi-PC-en.

**Adresse:** samme IP og port som Companion sitt web-grensesnitt, som standard `http://127.0.0.1:8000`.

### HTTP remote control (brukes i drift)

| Metode | Sti | Brukes til |
| --- | --- | --- |
| `POST` | `/api/location/<side>/<rad>/<kol>/press` | Trykk og slipp en knapp (preview, TAKE, makro) |
| `POST` | `/api/location/<side>/<rad>/<kol>/down` og `/up` | Holde inne og slippe (brukes ikke av motoren) |
| `POST` | `/api/location/<side>/<rad>/<kol>/style?text=…&bgcolor=…` | Endre tekst og farge på en knapp |
| `POST` | `/api/custom-variable/<navn>/value?value=<verdi>` | Skrive `regi_*`-variablene |
| `POST` | `/api/custom-variable/<navn>/value` med JSON-kropp | Skrive tall, sann/usann eller objekter |
| `GET` | `/api/custom-variable/<navn>/value` | Lese, f.eks. `cutcut_pages_version` |
| `GET` | `/api/variable/<tilkobling>/<navn>/value` | Lese en variabel fra en modul, f.eks. ATEM- eller Pearl-modulen |
| `GET` | `/api/connections` | Liste over tilkoblinger med status (fra 4.3) |
| `GET` | `/api/connections/<id>/status` | Status for én tilkobling |
| `POST` | `/api/connections/<id>/restart` | Starte en tilkobling på nytt (bare fra helse-siden, aldri automatisk under opptak) |

Gamle stier som `/press/bank/…` og `/set/custom-variable/…` er avviklet og brukes ikke.

### Helse og metrikk

- `GET /api/connections` gir status for ATEM- og Pearl-modulen i Companion; inngår i sjekken `H-COMP-1`.
- **Prometheus-metrikk** på `/api/metrics` (av som standard, slås på under *Settings → Protocols*, krever eget token): versjon (`companion_build_info`), antall knapper og tilkoblinger, og status og omstarter per tilkobling. CutCut leser denne hvert minutt hvis den er på.
- **REST API v2** på `/api/v2` (5.1 og nyere, av som standard, krever API-nøkkel med begrensede rettigheter) dekker foreløpig bare tilkoblinger og overflater. Den beskrives i `/api/v2/docs`. Brukes bare som reserve for helse.

### Sikkerhet

- HTTP remote control har ingen innlogging. Den sikres ved at Companion bare er tilgjengelig fra regi-PC-en og teknikernes maskiner (Windows-brannmur), og at studionettet er et eget VLAN.
- Admin-passord slås på under *Settings → Advanced*; det beskytter bare oppsettet, ikke API-et.
- Kjøring av kommandoer fra Companion og installasjon av moduler fra andre maskiner er av som standard og skal forbli av.
- Stream Deck kan låses med PIN etter tidsavbrudd.

### Oppsett som fil

- Side 10 og 11 lagres som eksport fra Companion (`cutcut-pages.companionconfig`) i studio-repoet, og importeres manuelt i Companion sitt grensesnitt. Det finnes ikke API for import.
- Eksporten inneholder custom variable `cutcut_pages_version`, som CutCut leser for å vite at riktig versjon er importert.

## OBSBOT Tail 2

**Beslutning:** begge protokollene snakker direkte med kameraet, og de brukes til det hver av dem gjør best.

- **VISCA over IP** (UDP 52381) til bevegelse, presets og zoom, fordi den har 256 presets, preset-fart og avlesing av posisjon, zoom, hvitbalanse og eksponering.
- **OSC** (UDP 57110 inn til kameraet, svar fra 57120) til fargetemperatur i kelvin og eksponeringsverdier, som VISCA mangler. Brukes ved oppsett og fargematching, aldri på kamera som er på lufta.
- **AI-tracking** er av som standard og slås på per kamera ved behov (regel AT1–AT6 i spesifikasjonen). CutCut kan slå den av og på per kamera med OSC SetAiEnable (se under). Kameraet sier ikke tilbake om tracking er på, så helsesjekken `H-CAM-MOVE` varsler hvis et kamera flytter seg uten at CutCut har bedt om det.
- **OBSBOT Center** brukes ikke.

### VISCA over IP (UDP 52381)

Fra OBSBOT sin kommandotabell for Tail 2. `pp`, `vv` osv. er verdier som forklart i merknaden.

| Funksjon | Kommando | Merknad |
| --- | --- | --- |
| Hent preset | `81 01 04 3F 02 pp FF` | `pp` = 00–FF |
| Lagre preset | `81 01 04 3F 01 pp FF` | Bare fra setup-hjelperen |
| Slett preset | `81 01 04 3F 00 pp FF` |  |
| Preset-fart (felles) | `81 01 7E 04 1C 0p 0p FF` | 01–19 |
| Pan/tilt med fart | `81 01 06 01 vv ww 0x 0y FF` | `vv` pan 01–18, `ww` tilt 01–17; retning: opp `03 01`, ned `03 02`, venstre `01 03`, høyre `02 03`, stopp `03 03` |
| Pan/tilt til posisjon | `81 01 06 02 vv ww 0p 0p 0p 0p 0t 0t 0t 0t FF` | Brukes til små utsnittsjusteringer |
| Hjem | `81 01 06 04 FF` |  |
| Les pan/tilt | `81 09 06 12 FF` | Svar `y0 50 0p 0p 0p 0p 0t 0t 0t 0t FF` |
| Zoom stopp | `81 01 04 07 00 FF` |  |
| Zoom inn/ut med fart | `81 01 04 07 2p FF` / `81 01 04 07 3p FF` | `p` = 0 (lav) til 7 |
| Zoom til verdi | `81 01 04 47 0z 0z 0z 0z FF` | Forholdet 1–12 × 1000 |
| Les zoom | `81 09 04 47 FF` |  |
| Fokus auto/manuell | `81 01 04 38 02/03 FF` | Les: `81 09 04 38 FF` |
| Fokus til verdi | `81 01 04 48 0p 0p 0p 0p FF` | 0000–0064; les: `81 09 04 48 FF` |
| Hvitbalanse-modus | `81 01 04 35 0p FF` | 0 auto, 1 inne, 2 ute, 5 manuell; les: `81 09 04 35 FF` |
| R-gain opp/ned | `81 01 04 03 02 FF` / `81 01 04 03 03 FF` | Les: `81 09 04 43 FF` (00–FF) |
| B-gain opp/ned | `81 01 04 04 02 FF` / `81 01 04 04 03 FF` | Les: `81 09 04 44 FF` (00–FF) |
| Eksponering-modus | `81 01 04 39 0p FF` | 0 full auto, 3 manuell; les: `81 09 04 39 FF` |
| Gain opp/ned | `81 01 04 0C 02/03 FF` | Les: `81 09 04 4C FF` |
| Lukker opp/ned | `81 01 04 0A 02/03 FF` | Les: `81 09 04 4A FF` |
| Lysstyrke direkte | `81 01 04 4D 00 00 0p 0q FF` | Les: `81 09 04 4D FF` |
| Motlys | `81 01 04 33 02/03 FF` | 2 på, 3 av |
| AI-tracking: modus, fart, auto-zoom, Only Me | `81 01 8E 01–04 … FF` | Les: `81 09 8E 01–04 FF`. Ingen ren av/på |

Hvitbalanse har ingen kelvin og ingen direkte R/B-verdi i VISCA. Driveren justerer derfor én verdi om gangen og leser tilbake til målet er nådd, med maks 100 steg per justering.

### OSC direkte til Tail 2

Fra OBSBOT sin OSC-definisjon for Tail 2. Kameraet er server: det tar imot på port **57110** (både UDP og TCP) og sender svar fra port **57120** (bare UDP). Over TCP støttes bare OSC 1.0. Ingen kommando har argument for valg av kamera; CutCut sender til hvert kameras egen IP-adresse.

| Funksjon | Adresse | Argumenter | Merknad |
| --- | --- | --- | --- |
| Tilkoblet | `/OBSBOT/WebCam/General/Connected` | `i` | Svar: `…/ConnectedResp` (1) og enhetsinfo. Brukes som hjerteslag |
| Frakoblet | `/OBSBOT/WebCam/General/Disconnected` | `i` | Sendes når CutCut avslutter |
| Enhetsinfo | `/OBSBOT/WebCam/General/GetDeviceInfo` | `i` | Svar: `…/DeviceInfo` |
| Les zoom | `/OBSBOT/WebCam/General/GetZoomInfo` | `i` | Svar: `…/ZoomInfo` med zoom 0–100 og synsfelt |
| Les vinkel | `/OBSBOT/WebCam/General/GetGimbalPosInfo` | `i` | Svar: `…/GetGimbalPosInfoResp` med tilt −90 til 90° og pan −140 til 140° |
| Zoom 0–100 % | `/OBSBOT/WebCam/General/SetZoom` | `i` 0–100 |  |
| Zoom med fart | `/OBSBOT/WebCam/General/SetZoomSpeed` | `ii` mål 0–100, fart 0–10 | Mulig vei for langsom zoom (`Z`) |
| Zoom maks/min | `…/SetZoomMax`, `…/SetZoomMin` | `i` |  |
| Kamerahode til vinkel | `/OBSBOT/WebCam/General/SetGimMotorDegree` | `iii` fart 0–90, pan −159 til 159°, tilt −62 til 62° | Absolutte grader |
| Kamerahode med fart | `…/SetGimbalUp`, `Down`, `Left`, `Right` | `i` 0–100 (0 = stopp) |  |
| Nullstill hode | `/OBSBOT/WebCam/General/ResetGimbal` | `i` |  |
| Speilvending | `/OBSBOT/WebCam/General/SetMirror` | `i` 0/1 |  |
| Fokus | `…/SetAutoFocus` (0/1), `…/SetManualFocus` (0–100) | `i` |  |
| Eksponering | `…/SetAutoExposure` (0/1), `…/SetExposureCompensate` (−30 til 30 i faste steg), `…/SetShutterSpeed` (f.eks. 100 = 1/100), `…/SetISO` (100–6400) | `i` | Lukker 100 passer 50 Hz-lys |
| Hvitbalanse | `…/SetAutoWhiteBalance` (0/1), `…/SetColorTemperature` (2000–10000) | `i` | Kelvin direkte: dette mangler i VISCA |
| AI-modus | `/OBSBOT/Camera/Tail2/SetAiMode` | `i` 0 enkeltperson, 1 flere | Ingen «av» |
| Tracking-fart | `/OBSBOT/Camera/Tail2/SetTrackingSpeed` | `iiiii` | 0 super lat – 4 gal, 5 egendefinert med pan/tilt manuell eller auto og fart 1–10 |
| Auto-zoom | `/OBSBOT/Camera/Tail2/SetAutoZoom` | `i` 0–7 | 0 = ingen; ellers nærbilde, halvfigur, over knærne osv. Settes til 0 |
| Only Me | `/OBSBOT/Camera/Tail2/SetOnlyMe` | `i` 0/1 | Settes til 0 |
| Kameraets presets | `/OBSBOT/Camera/Tail2/TriggerPreset` | `i` 0–2 | Bare tre; VISCA-presets brukes i stedet |
| Opptak og stillbilde i kameraet | `…/Tail2/SetRecording`, `…/Tail2/Snapshot` | `i` | Brukes ikke |

**AI-tracking av og på (ikke i OBSBOT sin tabell):** `/OBSBOT/Camera/Tail2/SetAiEnable` med `i` 0 = av, 1 = på. Kommandoen brukes av Bitfocus sin offisielle Companion-modul `companion-module-obsbot-osc` fra versjon 1.2.0 (oktober 2026), handlingen «Tail 2 | AI Mode On/Off». Modulen opplyser også at Tail 2 skriver lengden på OSC-pakker over TCP i omvendt byte-rekkefølge (little-endian), mens OBSBOT Center bruker big-endian; CutCut bruker derfor UDP.

**Det OSC ikke har:** avlesing av om tracking er på, lagring av presets, R/B-gain, og avlesing av hvitbalanse og eksponering. Etter en fargejustering via OSC bekreftes resultatet derfor med VISCA-avlesing av R/B-gain og med måling i multiview-bildet.

**Test ved første oppsett:** at OSC-svar kommer tilbake fra port 57120 gjennom brannmuren; at fargetemperatur via OSC og R/B-avlesing via VISCA stemmer overens; og at kameraet står stille med AI-tracking slått av i 10 minutter. Definisjonsfilen lagres som `site/<studio>/equipment/obsbot/OBSBOT_Tail_2_-_OSC_Definition.xlsx`.

## Blackmagic ATEM

- **Protokoll:** Blackmagic sin egen ATEM-protokoll over UDP port 9910. Biblioteket `atem-connection` (Node.js) støtter alle ATEM-modeller over nett, ikke over USB. I Python finnes PyATEMMax for lesing; velges ved første implementasjonsplan etter test mot riktig modell.
- **Brukes til:** lese program, preview, tally, SuperSource, makroer, mediaspillere, multiview og opptaksstatus; starte og stoppe opptak; direkte kutt som reserve.
- **Modeller:** ATEM Mini Extreme ISO (2 HDMI ut) og Extreme ISO G2 (3 HDMI ut, ISO til CFexpress eller USB-C, 10G). Støtte for G2 i `atem-connection` og Companion må bekreftes før innkjøp.
- **SuperSource-koordinater:** x −48 til +48, y −27 til +27, størrelse 1,0 = hele bildet. Startverdier for layoutene står i spesifikasjonen 7.2.
- **Fastvare:** ny ATEM-fastvare kan endre protokollen. Låses i produksjon og testes mot biblioteket før oppdatering.

## Epiphan Pearl Nexus

- **API:** REST v2.0 under `/api/v2.0`, Basic-autentisering, fra fastvare 4.24.1. OpenAPI-beskrivelsen ligger i GitHub-repoet `epiphan-video/pearl_api_swagger_ui` (`api/v2.0/openapi.yml`).

| Metode | Sti | Brukes til |
| --- | --- | --- |
| `GET` | `/recorders` og `/recorders/status?ids=…` | Opptakere og tilstand: `disabled`, `starting`, `started`, `stopped`, `error`, med varighet |
| `POST` | `/recorders/control/start?ids=…` | Start opptak (asynkront: les status etterpå) |
| `POST` | `/recorders/control/stop?ids=…` | Stopp opptak |
| `GET` | `/inputs` | Innganger med `nosignal` og oppløsning |
| `GET` | `/channels` | Kanaler og layouter |
| `GET` | `/system/status` | Oppetid, `cpuload`, `cputemp`, `cputemp_threshold` |
| `GET` | `/system/storages` | Lagring og ledig plass |
| `GET` | `/system/firmware/version` | Fastvareversjon |
| `GET`/`POST` | `/schedule/events` | Planlagte og ad-hoc-opptak (Panopto, Kaltura, Opencast) |
| `POST` | `/schedule/events/adhoc/session` | Kort innloggingsøkt (1 time) mot Panopto med brukerens pålogging |
| `POST` | `/schedule/events/{id}/control/start`, `stop`, `pause`, `resume`, `extend` | Styre et planlagt opptak |

- **Companion-modul** (`companion-module-epiphan-pearl`): start og stopp opptak og strømming, bytte kanallayout, sette tittel, forfatter og filnavn, sette markør.

## Canon CR-N300

- **XC-protokollen** over HTTP er Canon sin protokoll for IP-styring, og dekker alt som finnes i kameraets web-grensesnitt: hvitbalanse (R/B og kelvin), iris, gain, lukker, ND, detalj, knee, metning, gamma, svartbalanse. Kameraet må stå i manuell modus for at verdiene kan settes.
- **VISCA over IP** støttes også («Standard (VISCA) Communication (IP)» i databladet).
- **Utganger:** HDMI (opptil 4K30, 1080p59.94) og 3G-SDI (opptil 1080p59.94); NDI|HX finnes men brukes ikke.
- **Mangler:** selve XC-kommandolisten er ikke offentlig på nett. Den hentes fra Canon (produktsøtte eller utviklerprogram) før driveren skrives, og legges i `site/<studio>/equipment/canon/`.

## Panasonic AW-UE (fase 2)

- HTTP: `http://<ip>/cgi-bin/aw_ptz?cmd=<kommando>&res=1` (bevegelse) og `/cgi-bin/aw_cam?cmd=<kommando>&res=1` (bilde). `#` kodes som `%23`.
- Eksempler: hent preset `%23R07` (preset 8), R-gain `OSG:39:800` og B-gain `OSG:3A:800` (hex, 800 = midt), hvitbalanse-modus `OAW:<n>`.
- Minst 40 ms mellom bevegelseskommandoer; ingen keep-alive.

## Sony BRC/SRG (fase 2)

- VISCA over IP på UDP 52381. Hvitbalanse: auto, inne, ute, én-trykk, ATW og manuell med R- og B-gain opp/ned.

## Lyd, capture, kort og skjerm

| Enhet | Teknisk | Viktig å vite |
| --- | --- | --- |
| RØDECaster Pro II | USB 1, multitrack på, pre-fader; RØDECaster ASIO-driver | Virtual Devices-driveren er ikke kompatibel med ASIO og installeres ikke. USB 2 gir bare stereomiks |
| INOGENI 4KXUSB3 | HDMI 1.4a inn og gjennomgang; USB 3.0 UVC; YUY2/NV12 ukomprimert, MJPEG bare på USB 2; 1080p50 støttet; strøm fra USB (5 V, 900 mA) | Ingen driver. Forsinkelse er ikke oppgitt og måles. Har egen VISCA-port (RS-232) som ikke brukes |
| ATEM webkamera-utgang (HD8 ISO) | 2 × USB-C; webkamera 720p/1080p i programmets bildefrekvens; Windows ser «Blackmagic Design» som webkamera. Kilde velges i ATEM Software Control: Outputs → Webcam Out | Alternativ til INOGENI (D-071). Ikke bekreftet at Multi View kan velges på HD8 ISO, at bildet er ukomprimert, eller at ISO-opptak går samtidig: testes (Q41, `docs/research/multiview-over-usb.md`) |
| ELATEC TWN3 MIFARE (USB) | Moduser: tastatur-emulering, virtuell COM-port, transparent. Settes opp med TWNConfig (skriptet bestemmer format: hex, omvendt hex, desimal) | Bruk samme skript og format som i Crestron-studioene. USB-ID i COM-modus: `09D8:0320` |
| Kort-API | adressen fra IT-avdelingen (settes i appen) | Nøkkel og svarformat kommer; skal gi brukernavn og visningsnavn |
| iiyama ProLite T2254MSC-B2AG | 21,5″, 1920 × 1080, PCAP 10 punkt over USB, HDMI og DisplayPort, USB-hub, VESA 100 | Fungerer med Windows uten driver; kortleseren kan sitte i hubben |
| ProDVX TMP-22X (senere) | 21,5″, PCAP 10 punkt, HDMI inn, USB, VESA 100, 12 V | Brukes som skjerm for samme nettside; ingen innebygd kortleser |

## Ressurser

Her ligger kildene. Filer som er lastet ned eller fått fra leverandør, legges også i studio-repoet under `site/<studio>/equipment/<leverandør>/`, så prosjektet ikke avhenger av at lenkene virker.

**Companion**

- [Brukerveiledning (beta)](https://companion.free/user-guide/beta/) · [HTTP remote control](https://companion.free/user-guide/beta/remote-control/http-remote-control) · [REST API v2](https://companion.free/user-guide/beta/remote-control/rest-api) · [Prometheus-metrikk](https://companion.free/user-guide/beta/remote-control/prometheus-metrics) · [Sikkerhet](https://companion.free/user-guide/beta/security)
- [Kildekode og utgaver på GitHub](https://github.com/bitfocus/companion/releases) · [ATEM-modul](https://github.com/bitfocus/companion-module-bmd-atem) · [Pearl-modul](https://github.com/bitfocus/companion-module-epiphan-pearl)
- Bitfocus brukerportal (krever innlogging): `https://user.bitfocus.io/product/companion`

**OBSBOT**

- [VISCA-tabell for Tail 2 (Google Sheets)](https://docs.google.com/spreadsheets/d/1HOVbZWITASwmUu9BV0-ym4kYDdp6IUGc/edit?gid=1649156710#gid=1649156710) · [VISCA-guide](https://www.obsbot.com/explore/obsbot-tail-air/visca-over-ip) · [OSC-side](https://www.obsbot.com/webcam/osc) · [Tail 2-ressurser](https://www.obsbot.com/explore/obsbot-tail-2)
- OSC-definisjon: `obsbot_center_osc_definition20260115.xlsx` (mottatt fra Multimediesenteret; legges i studio-repoet). OSC-mappe på Google Drive: `https://drive.google.com/drive/folders/1mPAMxL3WokRQ6JBJcrK54hh9KMR3q4pA`

**Blackmagic**

- [ATEM Mini Extreme, spesifikasjoner](https://www.blackmagicdesign.com/products/atemmini/techspecs/W-APS-17) · [ATEM Mini Extreme ISO G2, spesifikasjoner](https://www.blackmagicdesign.com/products/atemmini/techspecs/W-APS-44) · [atem-connection (npm)](https://npmjs.com/package/atem-connection)

**Epiphan**

- [Pearl REST API v2.0 (OpenAPI)](https://github.com/epiphan-video/pearl_api_swagger_ui) · [REST-API i fastvare 4.24.1](https://www.epiphan.com/product-news/new-firmware-update-control-system-updates-rest-api-usb-button-led-light-support-and-easy-file-sharing/) · [Pearl Nexus brukerveiledning](https://www.epiphan.com/userguides/pearl-nexus/Content/Home-Pearl-Nexus.htm)

**Kamera fra andre produsenter**

- [Canon CR-N300 datablad](https://www.fullcompass.com/common/files/60067-CRN300DataSheet.pdf)
- [Panasonic AW-UE150 grensesnitt](https://eww.pass.panasonic.co.jp/pro-av/support/content/guide/DEF/UE150/AW-UE150HE145_InterfaceSpecification_E.pdf) · [Sony BRC/SRG VISCA over IP](https://applicationmarket.crestron.com/content/Help/Sony/Sony_BRC-X400_SRG-X_series_Help_v1.0.pdf)

**Lyd, capture, kort og skjerm**

- [RØDECaster Virtual Devices og ASIO](https://help.rode.com/hc/en-us/articles/11891033629839-What-is-the-Virtual-Devices-Driver-for-the-R%C3%98DECaster-Pro-II-Duo) · [RØDECaster USB-oppsett](https://rode.com/en-si/user-guides/rodecaster-pro-ii/a-guide-to-setting-up-usb-connections-on-the-rodecaster-pro-ii)
- [INOGENI 4KXUSB3 datablad](https://www.fullcompass.com/common/files/88448-4KXUSB3SpecSheet.pdf) · [Produktside](https://inogeni.com/product/4kxusb3/)
- [ATEM Television Studio HD8 ISO, tekniske data](https://www.blackmagicdesign.com/products/atemtelevisionstudio/techspecs/W-APS-21) · [ATEM Mini Extreme ISO G2, tekniske data](https://www.blackmagicdesign.com/products/atemmini/techspecs/W-APS-17)
- [ELATEC TWN3 MIFARE datablad](https://www.ELATEC-rfid.com/fileadmin/Documents/Data-Sheet/elatec-twn3-mifare-data-sheet-en.pdf) · [Oppsett av TWN-lesere med TWNConfig](https://cdn1.papercut.com/files/mf/docs/PaperCut%20MF%20-%20General%20Elatec%20TWN%20Reader%20Tasks%20-%202016-06-15.pdf)
- [iiyama ProLite T2254MSC-B2AG](https://iiyama.com/ie_en/products/prolite-t2254msc-b2ag/) · [ProDVX TMP-22X](https://www.prodvx.com/products/3022105-tmp-22x)

**Modeller og forskning**

- [Silero VAD](https://pypi.org/project/silero-vad) · [Light-ASD](https://ar5iv.labs.arxiv.org/html/2303.04439) · [NB-Whisper](https://huggingface.co/NbAiLabBeta/nb-whisper-medium/blob/4b385df7b3683972d66b7165837267cdd52f978f/README.md?code=true) · [Whisper-Streaming](https://arxiv.org/html/2307.14743) · [Voice Activity Projection](https://arxiv.org/html/2401.04868v1)
