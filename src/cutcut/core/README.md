# `cutcut.core` – regimotoren

Motoren bestemmer hva som legges på preview og program (spesifikasjonen 5). Plan: [`docs/plans/core.md`](../../../docs/plans/core.md).

## Slik er den bygget

- **Ren kjerne (PL-04, I3):** `Engine.step(Inputs) -> StepResult` uten klokke, I/O, tråder eller tilfeldighet. Samme inndata gir alltid samme beslutninger; det testes.
- **Inn** (`inputs.py`): målinger per mic fra `audio-capture` (`MicFrame`), video per rute (`TileFrame`), content-tilstand, ATEM-tilstand, kameraer i bevegelse og operatørkommandoer.
- **Ut**: beslutninger (`Decision`, spes. 5.8) og ønsker til utstyret (`intents.py`: `SetPreview`, `PrepareLayout`, `Take`, `DirectCut`, `ShowAudioOnly`, `SetCompanionVariable`). Skallet (K-9) utfører ønskene via Companion og `atem-bridge`.
- **Etter omstart (K-9):** AUTO, LÅS, content og skyggemodus hentes fra SQLite; bildet hentes fra ATEM; motoren venter `manual_quiet_s` (5 s) før første kutt.
- **Skyggemodus (PL-05):** motoren beslutter og logger (`shadow: true`), men sender ingenting.
- **Layouter (5.6, `L1`–`L4`, P3):** når bryteren `layouts` er på, kan motoren bytte ut taler-, krysstale- og ping-pong-bildet med en layout: `PIP:Px+CONTENT` når taleren har snakket 4 s og content er aktivt og vist siste 20 s (`L1`), `PIP:Px+Py` ved ping-pong mellom to (`L2`), `QUAD4` når tre eller flere har snakket siste 10 s i `N4` (`L3`), og `QUAD3C` med content og tre personer (`L4`). Content, innskudd, stillhet og latter blir som i grunnmodus. En layout står minst `L_min_s` og brukes ikke igjen innen `L_no_repeat_s`. Showet kan utelate en layout (`layouts:` i show-filen). Layouten lages med makro og tas med MIX, og regnes på lufta når ATEM bekrefter.
- **Vekslende utsnitt og langsom zoom (`F1`–`F3`, `Z1`–`Z3`, P4):** når et nærbildekamera går av program og preview, får det det andre utsnittet (`tight`/`wide`-preset) mens det er av lufta (`FrameCamera`), og kan ikke klippes til før det har stått stille (`F2`). Kandidaten til neste kutt flyttes aldri (`F3`). Med langsom zoom zoomer motoren litt inn på en taler som har stått en stund (`SlowZoom`, høyst 10 % over 10–20 s), stopper straks et annet bilde er klart (`StopZoom`), og bare på kameraer med `slow_zoom: true` i showet. Kamerakommandoene går til `CameraService`, ikke Companion; vakten slipper bare små, langsomme zoomsteg gjennom på lufta (I2s eneste unntak).
- **AI-tracking (`AT1`–`AT6`, P5):** tracking slås på per OBSBOT-kamera fra Kameraer-siden, Stream Deck (samme API) eller show-typen (`ai_tracking: [C2]`), aldri på fugleperspektivet. Først settes én person, fart «Lazy», auto-zoom av og «Only Me» av (`AT2`). Mens tracking er på, flytter ikke CutCut kameraet: utsnitt, zoom og presets er sperret, også i kameravakten (`AT3`). Kameraet regnes som i bevegelse (`S1`) bare over 3 °/s, og videolagets bevegelse teller ikke for det (`AT4`). Av er alltid lov; kameraet står der det er (`AT5`), og tracking slås av ved oppstart og når økten slutter (`AT6`).
- **Videobekreftelse og reaksjoner (`V1`–`V5`, `PV3`, `R1`–`R3`, P7):** med `video_confirm` korter munnbevegelse i riktig kamera ned `T2` (× `V1_factor`), og en aktiv mic med stille munn i `V1_leak_ms` regnes som lekkasje. Et bilde uten gyldig ansikt (`V2`) eller som beveger seg (`V5`) brukes ikke, og preview må ha stått stille i `V5_still_s` før `TAKE` (`PV3`). Et ansikt som sitter feil i et nærbilde av lufta rettes med små steg (`V4`, `NudgeCamera`). Med `reactions` får en lytter som smiler, nikker eller ler et reaksjonsbilde i talerens neste pause (`R1`), høyst ett per `R2_min_gap_s` og aldri på korte svar (`R2`); begynner lytteren å snakke, gjelder taler-reglene (`R3`). Reaksjonsbildet i lange svar viser den som reagerer mest (`V3`). `V6` (blikkretning) er eksperimentell og ikke bygget.
- **Skygge per bryter (F-1):** hver bryter utover grunnmodus (`video_confirm`, `reactions`, `framing_variety`, `slow_zoom`, `layouts`, `ai_tracking`) er av, i skygge eller på (`Features.mode`). I skygge kjører reglene og logges med `switch` satt og `shadow: true` (samme notat høyst hvert 2. sekund), men kuttene er grunnmodusens. Feiler en bryters regler, regnes den som av (`failed_switches`), og `Studio` flytter den til skygge og varsler gult. Teknikervinduet viser hvorfor en bryter ikke kan slås på (`rules.switches`).

| Fil | Innhold |
| --- | --- |
| `inputs.py` | Inndata og kommandoer |
| `intents.py` | Ønsker til utstyret |
| `content.py` | Content-tilstand fra laptop-ruta og laptop-lyd (`CT1`–`CT6`) |
| `speakers.py` | Hvem snakker: `T1`, `T12`, `S6`, krysstale, latter og turbytter (`T6`) |
| `shots.py` | Bildeutvalg per modus (5.1) og bilde ↔ ATEM-kilde |
| `messages.py` | Busmeldinger som motoren leser (`audio.frame`, `vision.content`, `vision.tile`, `atem.state`, `cameras.moving`) |
| `runtime.py` | Skallet: tikk hvert 30. ms, mater motoren, logger beslutninger, sender ønsker til en `Executor`, lagrer innstillinger hvert sekund og gjenoppretter dem etter omstart |
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

## Sporbarhet

`uv run python tools/traceability.py` skriver `docs/reference/traceability.md` (regel → kode → antall tester) og `docs/reference/rules.md` (alle regelverdier per forhåndsvalg). CI feiler hvis en implementert regel mangler test eller kode, eller hvis de genererte filene er utdaterte (spesifikasjonen 12.1). Regler for senere milepæler står i `PLANNED` i skriptet.
