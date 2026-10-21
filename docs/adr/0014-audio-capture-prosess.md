# ADR-0014: Lyd via RØDE ASIO i egen prosess `audio-capture`

- **Status:** Forslag (avgjøres etter maskintest, Q21)
- **Dato:** 2026-10-21
- **Kilde:** beslutningslogg D-031; `docs/research/lyd-fra-rodecaster.md`

## Kontekst

Motoren trenger alle mic-er som sample-synkrone spor med lav, stabil forsinkelse i måneder. Spesifikasjonen 3 legger lydinngangen i `core`. En ASIO-driver som henger ved USB-feil vil da kunne henge motoren.

## Beslutning

- RØDECaster ASIO-driver, én strøm med alle 20 multitrack-kanaler (48 kHz, pre-fader), via `sounddevice` med `SD_ENABLE_ASIO`.
- Lyden leses i en egen prosess, `audio-capture`, under supervisor, som sender per-kanal-blokker til `core`.
- Kanalkart etter fader-posisjon (firmware ≥ 1.7.3), bekreftet i setup-hjelperen.
- WASAPI (Windows' egen driver) som reserve bak samme grensesnitt (`audio.backend`).

## Konsekvenser

Én prosess til. `core` må tåle at lyden forsvinner (`S4`) og komme tilbake når `audio-capture` er startet på nytt. Erstatter «lyd i core» i spesifikasjonen 3 og 12.2 når den godkjennes.
