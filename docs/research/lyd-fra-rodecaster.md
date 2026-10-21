# Research: lyd fra RØDECaster Pro II inn i CutCut

Dato: 2026-10-21 · Status: anbefaling, må bekreftes med maskintest (Q21)

## Spørsmålet

Motoren trenger hver mikrofon som et eget, rent spor med lav og stabil forsinkelse, sample-synkront mellom kanalene (for dominans og lekkasjematrise), døgnet rundt i måneder. Hvordan får vi det best inn i en Python-prosess på Windows?

## Det vi vet om RØDECaster Pro II

| Fakta | Kilde |
| --- | --- |
| Multitrack over USB går bare på **USB 1**. USB 2 gir bare stereo | RØDE, multitrack-guider |
| Windows trenger **RØDECaster ASIO-driveren** for multitrack i DAW-er | RØDE, Hindenburg-guide |
| Fra firmware **1.7.3** er multitrack-kanalene ordnet etter **fader-posisjon**: 1–2 hovedmiks, 3–4 fader 1, 5–6 fader 2 … 19–20 fader 9. Alle utganger er stereo; mono-kilder (Combo/XLR) kommer som dobbel mono | RØDE, «Multitrack Channel Layout» |
| Eldre guider viser 16 kanaler med fast rekkefølge per inngang. **Utdatert** etter 1.7.3 | RØDE, Reaper-guide |
| **Pre-fader** sender alle kilder med enhetsforsterkning *før* prosessering og fader | RØDE, Reaper-guide |
| **Virtual Devices-driveren** gir hver fader som egen Windows-inngang («Fader 1»–«Fader 9»), brukt av OBS. Den er **ikke kompatibel med ASIO**: de kan ikke brukes samtidig | RØDE, Virtual Devices- og OBS-artikler |
| Virtual Devices krever at RØDE sin systemstatus-app kjører og at «Bypass» er av | RØDE, feilsøking |
| Samplingsfrekvens 48 kHz | RØDE, multitrack-guider |

## Det vi vet om programvaren

| Fakta | Kilde |
| --- | --- |
| `sounddevice` (pip) har med to PortAudio-DLL-er på Windows; den med ASIO lastes når miljøvariabelen `SD_ENABLE_ASIO` er satt før import | python-sounddevice, installasjon |
| Steinberg lisensierte ASIO SDK som **GPLv3 eller proprietær** fra oktober 2025. Lisens er ikke lenger et hinder for åpen kildekode, og intern bruk er uansett uproblematisk | Steinberg / LibreArts |
| Silero VAD tar **512 sampler ved 16 kHz (32 ms)** per kall. Spesifikasjonen 3.1 sier 30 ms; riktig er 32 ms | silero-vad wiki |

## Alternativer

| | A. ASIO (anbefalt) | B. Virtual Devices + WASAPI | C. Windows' egen USB-lyddriver + WASAPI |
| --- | --- | --- | --- |
| Driver | RØDECaster ASIO | RØDECaster Virtual Devices + tray-app | Ingen fra RØDE (class compliant) |
| Strømmer | Én strøm, alle kanaler | Én strøm per fader | Én flerkanals strøm |
| Sample-synkront mellom mic-er | Ja, garantert | Nei, separate buffere; forskyvning må måles og korrigeres | Ja, hvis Windows viser alle kanaler |
| Forsinkelse | Lavest, fast buffer | Delt modus med mikser i Windows; høyere og mer variabel | Lav i eksklusiv modus |
| Flere programmer samtidig | Normalt ett program per ASIO-driver | Ja | Eksklusiv: nei; delt: ja |
| Avhengighet av tray-app | Nei | Ja (må kjøre, Bypass av) | Nei |
| Dokumentert av RØDE for multitrack | Ja | Ja (for OBS) | Nei, må testes |
| Risiko | Driver låser seg ved USB-feil; må gjenåpnes | Flere bevegelige deler; ukjent oppførsel over måneder | Usikkert om alle 20 kanaler vises |

## Anbefaling

1. **A: ASIO** med `sounddevice` (`SD_ENABLE_ASIO=1`), én inngangsstrøm med alle 20 kanaler, 48 kHz. Det er det RØDE dokumenterer for multitrack, det eneste som garanterer synkrone kanaler, og det har færrest deler. Spesifikasjonen 2.3 står (ASIO-driver, ikke Virtual Devices).
2. **Lyden i en egen liten prosess, `audio-capture`.** Den åpner ASIO, leser blokker, og publiserer per-kanal-rammer over den interne bussen (eller delt minne) til `core`. Feiler driveren, er det denne prosessen som henger eller krasjer, ikke motoren; supervisor starter den på nytt, og `core` følger `S4` (kutt til `BIRD`, AUTO på pause) imens. Dette er en endring fra spesifikasjonen 3 (lyd i core) og foreslås som ADR-0014.
3. **Kanalkart fra faderne, ikke fra inngangene.** Konfig sier hvilken fader hver mic står på; kanalen er `2 × fader + 1` (venstre i paret, 1-basert). Setup-hjelperen bekrefter kartet med «snakk i mic N» før baseline godkjennes, og helsesjekken `H-AUD` varsler hvis signal dukker opp på feil kanal. Firmware låses (≥ 1.7.3) og noteres i `versions.yaml`.
4. **Signalkjede i appen:** 48 kHz → lavpass og nedsampling til 16 kHz per mic → Silero VAD i blokker på 512 sampler (32 ms) → nivå og lekkasje på de samme blokkene; frasegrenser på 10 ms-rammer fra 48 kHz-signalet. Buffer i ASIO: start med 256 sampler (5,3 ms) og øk ved dropouts.
5. **B og C som reserve bak samme grensesnitt** (`audio.backend: asio | wasapi`), slik at et driverproblem kan omgås uten kodeendring. B brukes ikke sammen med A (RØDE sier de ikke kan kjøre samtidig).

## Windows-oppsett som må med i setup-hjelperen (steg 2)

- RØDECaster på USB 1, direkte i PC-en (ingen hub), USB 3-port.
- USB-strømsparing av (strømplan og enhetsbehandling).
- RØDECaster: Multitrack → USB 1 Output → **Pre-Fader**. Virtual Devices-driveren **ikke** installert.
- Samplingsfrekvens 48 kHz.
- Ingen andre programmer skal åpne RØDECaster ASIO (ATEM og Pearl får lyd via hovedmiks/HDMI, ikke fra PC-en).

## Maskintest: `tools/hw-test/audio_rodecaster.py`

Skal svare på Q21 og bekrefte anbefalingen. Måler og rapporterer:

1. ASIO-enheten finnes, navn, antall inngangskanaler (forventet 20), støttede buffere.
2. Kanalkart: tekniker snakker i hver mic; skriptet finner kanalen med signal og sammenligner med konfig.
3. Synkronitet: klapp foran alle mic-er; krysskorrelasjon mellom kanalene (forventet 0 sampler forskyvning).
4. Forsinkelse og dropouts: 60 minutter opptak med teller for over- og underflyt per buffer-størrelse (128/256/512).
5. Gjenoppretting: trekk ut USB, slå RØDECaster av og på; måler tid til strømmen er åpen igjen.
6. Samme målinger for C (WASAPI eksklusiv) hvis Windows viser kanalene, så vi vet om reserven virker.

Resultatet legges som issue med malen «Maskintest-rapport», og avgjør ADR-0014.

## Kilder

- RØDE: [Multitrack Channel Layout (1.7.3)](https://help.rode.com/hc/en-us/articles/15412830674959-The-R%C3%98DECaster-Pro-II-Duo-Multitrack-Channel-Layout) · [Multitrack i Reaper, PC (PDF)](https://edge.rode.com/pdf/page/2015/modules/8/RCPII_Multitrack_Guidelines_Reaper_PC.pdf) · [Multitrack i Hindenburg, Windows](https://help.rode.com/hc/en-us/articles/8961922716175-How-to-setup-Multitrack-with-the-R%C3%98DECaster-Pro-II-Duo-in-Hindenburg-Windows) · [Virtual Devices og ASIO](https://help.rode.com/hc/en-us/articles/11891033629839-What-is-the-Virtual-Devices-Driver-for-the-R%C3%98DECaster-Pro-II-Duo) · [Virtual Devices multitrack](https://help.rode.com/hc/en-us/articles/15514570006927-The-R%C3%98DECaster-Pro-II-Duo-Virtual-Devices-Multitrack-Output) · [OBS multitrack](https://help.rode.com/hc/en-us/articles/6798161158671-How-to-use-your-R%C3%98DECaster-Pro-II-Duo-with-OBS-Multitrack) · [Feilsøking Virtual Devices](https://help.rode.com/hc/en-us/articles/17014520517007-Troubleshooting-R%C3%98DECaster-Pro-II-Duo-Virtual-Devices-on-Windows)
- [python-sounddevice: installasjon og ASIO](https://python-sounddevice.readthedocs.io/en/0.5.5/installation.html)
- [LibreArts: Steinberg relisensierer VST3 og ASIO](https://librearts.org/2025/11/steinberg-relicenses-vst3-and-asio/)
- [Silero VAD: blokkstørrelser](https://github.com/snakers4/silero-vad/wiki/Examples-and-Dependencies)
- [Audacity-forum: RØDECaster multikanal over WASAPI](https://forum.audacityteam.org/t/multitrack-recording-isnt-working-anymore-option-for-14-channels-isnt-there-rodecaster-pro/150733) (første generasjon, indikasjon for alternativ C)
