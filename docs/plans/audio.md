# Plan: `audio` – lyd fra RØDECaster (`audio-capture`)

Status: forslag (M0) · Milepæl: M2 · Spes. 2.3, 3.1, 5.3, 5.7 (`S4`, `S6`), 5.10, 8.4 steg 5, 8.5 (`H-AUD-*`); D-031, D-032, D-035; ADR-0014; `docs/research/lyd-fra-rodecaster.md`, `docs/studio/rodecaster-standardoppsett.md` · Mappe: `src/cutcut/audio/`

## 1. Formål og avgrensning

Gi motoren pålitelige målinger per mikrofon døgnet rundt: hvem snakker, hvor sterkt, hvor er pausene og setningsslutt, og hvem er dempet på mikseren. Dekker regelgrunnlaget for `T1`, `T4`, `T9`, `K1`–`K4`, `S4`, `S6`, lydsjekken under nedtellingen på touch og mic-sjekken i setup-hjelperen (steg 5).

**ADR-0014 bekreftes med presisering (PL-02):** prosessen `audio-capture` både leser lyden *og* analyserer den, og sender bare målinger til `core`. Begrunnelse:

- `core` blir ren regelkode (PL-04) og kan kjøres i simulator og nettleser uten lydbiblioteker.
- Et driverheng rammer bare `audio-capture`; `core` følger `S4` og fortsetter.
- Bussen bærer noen hundre små meldinger per sekund i stedet for 20 kanaler rå lyd.
- Rå lyd sendes bare til `stt` når bryteren `live_transcript` er på (eget emne).

## 2. Grensesnitt

**Signalkjede (fra research):** ASIO, 20 kanaler, 48 kHz, buffer 256 → kanalkart etter fader (`2 × N + 1`) → per mic: nedsampling til 16 kHz → Silero VAD i 512-sampler-blokker (32 ms) → nivå, dominans og lekkasje på samme blokker → frasegrenser (pause, energifall, YIN-tonehøyde) på 10 ms-rammer.

**Ut på bussen:**

| Emne | Takt | Innhold |
| --- | --- | --- |
| `audio.frame` | 100 Hz (10 ms) | Per mic `M1`–`M5`: `vad`, `level_db`, `dominance_db`, `active`, `pause_ms`, `phrase_end`, `pitch_falling`, `in_main_mix`, `leak_from` |
| `audio.meters` | 20 Hz | Topp og RMS per mic for skjermene |
| `audio.status` | 1 Hz + ved endring | Backend, enhet, buffer, over-/underflyt, kanalkart OK, siste feil |
| `audio.pcm` | bare med `live_transcript` | 16 kHz mono per mic til `stt` |

**Lekkasjematrise:** målt i setup-hjelperen (steg 5: én og én snakker), lagret i `baseline.yaml`. I drift: aktiv mic regnes som lekkasje hvis nivået forklares av en annen aktiv mic gjennom matrisen (+ margin).

**`S6` dempet på mikser:** hovedmiksen (kanal 1–2) sammenlignes med hver mic. Er mic-en aktiv, men korrelasjonen med hovedmiksen lav i over 0,5 s, settes `in_main_mix = false`. Krever Q24-svar for å vite om det trengs.

**Backend bak grensesnitt** (`audio.backend: asio | wasapi | fake`): ASIO først, WASAPI eksklusiv som reserve, `fake` for Linux og tester.

## 3. Tilstander og feil

| Situasjon | `audio-capture` gjør | `core` gjør |
| --- | --- | --- |
| ASIO-strømmen stopper eller USB trekkes ut | Lukker, prøver å åpne igjen hvert 5. sekund (9.1); `audio.status` rød | Etter 2 s uten `audio.frame`: `S4` |
| Prosessen henger (ingen hjerteslag) | Supervisor dreper og starter den | `S4`, så tilbake når målinger kommer |
| Over-/underflyt | Teller; flere enn 5 per minutt gir gult og forslag om større buffer | – |
| Signal på feil kanal (kanalkart endret, f.eks. ny firmware) | Gult `H-AUD-1` med forklaring | Fortsetter |
| Støy i stillhet over fasit + 6 dB | Gult `H-AUD-2` | Fortsetter |

Rå lyd lagres aldri på disk (personvern), unntatt i maskintest og setup når tekniker ber om det.

## 4. Avhengigheter

`sounddevice` (PortAudio med ASIO, `SD_ENABLE_ASIO=1`), `numpy`, `onnxruntime` (CPU) med Silero VAD (MIT, versjon og SHA-256 i `models/manifest.yaml`), `soxr` eller `scipy` for nedsampling. Utstyr: RØDECaster Pro II, firmware 1.7.6, RØDE ASIO-driver.

## 5. Testplan

- Enhetstester på syntetiske signaler: VAD-terskel, dominans, pause, fallende tonehøyde, lekkasje, `S6`.
- Gylne filer: kjente WAV-snutter (selvlaget, ingen persondata) gir kjente `audio.frame`-forløp.
- Tidsbudsjett: en 10 ms-ramme for 5 mic-er analyseres på under 3 ms på CI-maskin.
- Avspilling av ekte multitrack fra Q1 (når den kommer) mot motoren.
- **Maskintest** `tools/hw-test/audio_rodecaster.py`: de sju punktene i research-notatet (enhet, kanalkart, synkronitet, 60 min dropouts, gjenoppretting etter USB-uttrekk, dempet kanal for Q24, WASAPI-reserve). Avgjør Q21, Q24 og ADR-0014.
- Soak: 72 timer i studio i skyggemodus (M2) uten minnevekst eller tapt strøm.

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| AU-1 | `audio.frame`-modell og `fake`-backend som spiller WAV | `core` kjører på den |
| AU-2 | VAD (Silero), nivå, dominans | Enhetstester grønne |
| AU-3 | Frasegrenser (pause, energi, YIN) | Gylne filer grønne |
| AU-4 | Lekkasjematrise og `S6`-signal | Tester grønne |
| AU-5 | ASIO-backend med gjenåpning, `audio.status`, WASAPI-reserve | Kjører på Windows i CI (self-hosted eller `windows-latest` uten lydkort, med `fake`) |
| AU-6 | Maskintestskript med rapport (JSON + Markdown) | Tekniker kan kjøre det fra én kommando |
| AU-7 | Lydsjekk for touch-nedtelling og setup steg 5 | Virker mot simulator og i studio |

## 7. Åpne spørsmål

- Q21 (ASIO stabilt med 20 kanaler) og Q24 (dempet mic i pre-fader-sporet): avgjøres av maskintesten.
- Q25: eksakte fargenavn på RØDECaster (bare for `baseline.yaml`).
- Q1: ekte multitrack-opptak til tuning og avspillingstester.
</content>
</invoke>
