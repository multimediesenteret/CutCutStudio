# `cutcut.app` – studioet som én tjeneste

`Studio` samler motor og skall, økt og touch-flyt, opptaker (Pearl), varsler og live-data for skjermene. All tilstand ligger her, ikke i skjermene (12.5). Samme klasse kjører i studio og i simulatoren; bare utstyret er ulikt (`StudioDeps`).

| Fil | Innhold |
| --- | --- |
| `studio.py` | `Studio`: tikk, kommandoer med revisjonslogg, tilstand for skjermene, live endring av forhåndsvalg, brytere og finjustering som overlever omstart (ADR-0011), økthistorikk |
| `state.py` | Typede modeller for tilstanden og live-meldingene (`StudioState`, `Meter`, `LiveMessage`). De står i `docs/reference/openapi.json`, og skjermenes typer genereres derfra |
| `export.py` | CSV av logg og økter, og feilsøkingspakken (zip uten hemmeligheter, personliste eller kortnummer) |
| `hub.py` | Fordeling av live-meldinger til skjermene, med begrenset kø per klient |

Antall personer på klar-skjermen velger show-oppsettet med det antallet deltakere fra `site/<studio>/shows/`.
