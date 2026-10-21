# ADR-0003: Tre prosesser (core, vision, stt) under en supervisor som kjører som Windows-tjeneste (WinSW)

- **Status:** Akseptert
- **Dato:** 2026-10-20
- **Kilde:** spesifikasjonen 0.3

## Kontekst

Feil i bildeanalyse eller tekst skal aldri stoppe klippingen.

## Beslutning

Tre prosesser (core, vision, stt) under en supervisor som kjører som Windows-tjeneste (WinSW).

## Konsekvenser

Prosessene snakker over intern meldingsbuss (ZeroMQ). core må virke alene.
