# `cutcut.common`

Felles grunnmur for alle moduler: modeller, konfig, klokke, logging, lagring, meldingsbuss og plattform-adaptere. Ingen regler og ingen enhetskode.

| | |
| --- | --- |
| Plan | [`docs/plans/common.md`](../../../docs/plans/common.md) |
| Status | C-2: `ids.py` (faste ID-er, bilder, moduser, regel-ID-er) og `models/` (show, økt, beslutning, buss). `config/`: lasting og validering av YAML, regelverdier per forhåndsvalg (`config/defaults/rules.yaml`), show-typer, migrering etter `schema_version`, JSON Schema til `config/schema/` (C-3). C-4 til C-8 gjenstår |
| Inn | YAML fra `config/defaults/` og `site/<studio>/` |
| Ut | Pydantic-modeller og tjenester brukt av alle andre moduler |
| Regel-ID-er | Ingen (regler ligger i `core`) |
| Akseptanse | Se testplanen i planen |

## Kommandoer

| Kommando | Gjør |
| --- | --- |
| `uv run python -m cutcut.common.config.schema` | Skriver JSON Schema til `config/schema/` etter endring i en konfigmodell. En test feiler hvis filene er utdaterte |
