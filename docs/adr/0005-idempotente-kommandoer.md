# ADR-0005: Alle enhetskommandoer er idempotente, har tidsavbrudd, går gjennom kø per enhet og har kretsbryter

- **Status:** Akseptert
- **Dato:** 2026-10-20
- **Kilde:** spesifikasjonen 0.3

## Kontekst

Én treg enhet kan ikke henge resten.

## Beslutning

Alle enhetskommandoer er idempotente, har tidsavbrudd, går gjennom kø per enhet og har kretsbryter.

## Konsekvenser

Kretsbryter-status vises på helsesiden (H-*).
