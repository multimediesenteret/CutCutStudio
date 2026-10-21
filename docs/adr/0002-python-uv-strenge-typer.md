# ADR-0002: Python 3.12 med strenge typer (mypy strict, Pydantic v2); avhengigheter låst med uv; egen Python i app-mappen

- **Status:** Akseptert
- **Dato:** 2026-10-20
- **Kilde:** spesifikasjonen 0.3

## Kontekst

Lyd- og modelløkosystemet finnes i Python; samme installasjon hver gang, uavhengig av system-Python.

## Beslutning

Python 3.12 med strenge typer (mypy strict, Pydantic v2); avhengigheter låst med uv; egen Python i app-mappen.

## Konsekvenser

Hver release pakker sin egen Python. Typesjekk er obligatorisk i CI.
