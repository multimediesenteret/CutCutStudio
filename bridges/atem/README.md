# atem-bridge

Liten Node-prosess mellom ATEM-mikseren og CutCut `core` (ADR-0012). Den har ingen logikk: den sender det ATEM viser, og utfører kommandoer fra `core`.

| Retning | Emne | Innhold |
| --- | --- | --- |
| bro → core | `atem.state` | Ved endring (samlet i 30 ms) og hvert sekund: `model`, `program_input`, `preview_input`, `multiview` (layout, preview til venstre, ruter, safe area, lydmålere, tally, videoformat), `recording` |
| bro → core | `atem.status` | `connected`, `last_error`, `model` hvert sekund |
| core → bro | `atem.cmd` | `{id, op: "cut" | "preview" | "run_macro", args}` |
| bro → core | `atem.ack` | `{id, ok, error}` |

Broen sender ATEM-inngangsnumre; `core` slår opp hva de er i studio-oppsettet (`cutcut.devices.atem.bridge.input_map`). Meldingene har samme konvolutt som resten av bussen (`src/cutcut/common/models/bus.py`) og går over ZeroMQ på `127.0.0.1:5560/5561`.

```bash
pnpm --filter @cutcut/atem-bridge start -- --ip 10.10.10.10   # startes av supervisor i studio
pnpm --filter @cutcut/atem-bridge test                         # kontrakttest
```

**Kontrakttest:** `src/translate.test.ts` lager `atem.state` for NTNU-studioet slik det så ut på bildet av multiviewen og sammenligner med `tests/fixtures/atem/state-ntnu.json`. Python-testene (`tests/integration/test_atem_bridge.py`) leser samme fil, så begge sider må være enige. Endres formatet: `UPDATE_FIXTURES=1 pnpm --filter @cutcut/atem-bridge test`.

**Bekreftes i maskintesten (DA-5):** at preview er venstre rute når «swap» er av, og hvilket kildenummer opptaksstatus-ruta har (rapporteres nå som `other`).
