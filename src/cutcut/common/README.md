# `cutcut.common`

Felles grunnmur for alle moduler: modeller, konfig, klokke, logging, lagring, meldingsbuss og plattform-adaptere. Ingen regler og ingen enhetskode.

| | |
| --- | --- |
| Plan | [`docs/plans/common.md`](../../../docs/plans/common.md) |
| Status | C-1: tom pakke. Innholdet bygges i C-2 til C-8 |
| Inn | YAML fra `config/defaults/` og `site/<studio>/` |
| Ut | Pydantic-modeller og tjenester brukt av alle andre moduler |
| Regel-ID-er | Ingen (regler ligger i `core`) |
| Akseptanse | Se testplanen i planen |
