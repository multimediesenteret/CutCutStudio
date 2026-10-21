# ADR-0013: Web-simulator med samme GUI, publisert på Vercel

- **Status:** Akseptert 2026-10-21 (D-046). Bekreftet i M0-planen `docs/plans/ui.md` og `sim.md`
- **Dato:** 2026-10-21
- **Kilde:** beslutningslogg D-029, D-030; `docs/simulator.md`

## Kontekst

Appen er en Windows-app som bare kan kjøres i studio. NTNU vil raskt kunne se og diskutere skjermer og klipping uten utstyr, og vise dem til andre.

## Beslutning

En statisk web-simulator på Vercel (Hobby) som bruker de samme UI-appene (`ui/apps/touch`, `ui/apps/tech`) med en simulert transport i stedet for WebSocket. Trinn 1: avspilling av scenarioer kjørt av Python-simulatoren i CI. Trinn 2: regelmotoren kjøres i nettleseren med Pyodide.

## Konsekvenser

Regelmotoren må være ren Python uten I/O, tråder eller Windows-avhengigheter (også krav for I3). UI-et må ha et transportlag som kan byttes. Ingen persondata eller ekte utstyr i simulatoren.

## Alternativer som ble vurdert

- Egen JavaScript-kopi av reglene: avvist, blir ulik den ekte motoren.
- Python-server på Vercel: avvist, krever langvarige forbindelser og gir ingen fordel over Pyodide.
