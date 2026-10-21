# ADR-0006: Oppsett som YAML i git med skjema; kjøredata i SQLite (WAL); logg som JSON-linjer

- **Status:** Akseptert
- **Dato:** 2026-10-20
- **Kilde:** spesifikasjonen 0.3

## Kontekst

Lett å lese, versjonere og gjenopprette.

## Beslutning

Oppsett som YAML i git med skjema; kjøredata i SQLite (WAL); logg som JSON-linjer.

## Konsekvenser

Konfig har schema_version og migreringer; CutCut starter ikke med ukjent versjon.
