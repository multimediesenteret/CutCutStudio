# `cutcut.core` – regimotoren

Motoren bestemmer hva som legges på preview og program (spesifikasjonen 5). Plan: [`docs/plans/core.md`](../../../docs/plans/core.md).

## Slik er den bygget

- **Ren kjerne (PL-04, I3):** `Engine.step(Inputs) -> StepResult` uten klokke, I/O, tråder eller tilfeldighet. Samme inndata gir alltid samme beslutninger; det testes.
- **Inn** (`inputs.py`): målinger per mic fra `audio-capture` (`MicFrame`), video per rute (`TileFrame`), content-tilstand, ATEM-tilstand, kameraer i bevegelse og operatørkommandoer.
- **Ut**: beslutninger (`Decision`, spes. 5.8) og ønsker til utstyret (`intents.py`: `SetPreview`, `PrepareLayout`, `Take`, `DirectCut`, `ShowAudioOnly`, `SetCompanionVariable`). Skallet (K-9) utfører ønskene via Companion og `atem-bridge`.
- **Skyggemodus (PL-05):** motoren beslutter og logger (`shadow: true`), men sender ingenting.

| Fil | Innhold |
| --- | --- |
| `inputs.py` | Inndata og kommandoer |
| `intents.py` | Ønsker til utstyret |
| `content.py` | Content-tilstand fra laptop-ruta og laptop-lyd (`CT1`–`CT6`) |
| `speakers.py` | Hvem snakker: `T1`, `T12`, `S6`, krysstale, latter og turbytter (`T6`) |
| `shots.py` | Bildeutvalg per modus (5.1) og bilde ↔ ATEM-kilde |
| `engine.py` | Prioritetsrekkefølgen (5.2), preview-tilstander (5.9), kuttpunkt (5.10), hold (5.11), sikkerhet (5.7), overstyring |

## Regel-ID-er modulen eier

| Gruppe | Status |
| --- | --- |
| `T1`–`T9`, `T12`, roller (5.12) | Ferdig |
| `PV1`, `PV4`, preview-tilstander | Ferdig. `PV2` håndheves i kameradriverne (M3), `PV3` med videolaget (M4) |
| `K1`–`K4`, `H1`–`H4` | Ferdig |
| `S1`–`S4`, `S6` | Ferdig. `S5` (Companion nede) avgjøres i skallet ved utføring |
| `B1`–`B5` | Ferdig |
| `CT1`–`CT6` | Ferdig (`content.py`): aktiv etter 2 s, ny slide, video og laptop-lyd, retur via kort fugleperspektiv, tapt signal kuttes bort straks |
| Overstyring (`MANUAL`): manuelt kutt, AUTO, LÅS, manuell preview, endring på ATEM av en person (I5), Kun lyd (`A`) | Ferdig |

## Valg som ikke står eksplisitt i spesifikasjonen

- **Vertens innskudd og krysstale:** når verten snakker over gjesten på lufta, regnes det ikke som krysstale (`T5`) før det har vart `T4_host_backchannel_s` (1,5 s). Det følger av 5.12, ellers ville et «mm» på 1,2 s gitt kutt til fugleperspektiv.
- **`T9`:** gjelder kutt som ikke skyldes ny taler (krysstale, stillhet, ping-pong): vent inntil 300 ms på en pause på minst 150 ms hos taleren.
- **Reaksjonsbilde (`T7`) og fugleperspektiv (`B5`)** veksler i lange svar. Retur (`H4`) legges på preview 0,6 s før innslaget er ferdig, og tas ikke hvis lytteren på skjermen har begynt å snakke (`R3`).
- **Åpning `B1`:** `StartShow` (opptak startet) gir fugleperspektiv i `B1_open_s` og så verten. Taler-reglene avbryter ikke åpningen eller det korte fugleperspektivet etter content.
- **`T3` ved retur** bruker grunnverdien uten gjestetillegget, så et reaksjonsbilde på 2,5 s ikke blir 3,5 s.

## Tester

`tests/rules/`: én test som slår til og én som ikke gjør det per regel-ID, tabelltester for modusene, og egenskapstester (hypothesis) som sjekker at `S1`, `S3`, `H2` og determinisme holder for tilfeldige samtaler. Ytelse: `step` under 2 ms i snitt.
