# `cutcut.app` – studioet som én tjeneste

`Studio` samler motor og skall, økt og touch-flyt, opptaker (Pearl), varsler og live-data for skjermene. All tilstand ligger her, ikke i skjermene (12.5). Samme klasse kjører i studio og i simulatoren; bare utstyret er ulikt (`StudioDeps`).

| Fil | Innhold |
| --- | --- |
| `studio.py` | `Studio`: tikk, kommandoer med revisjonslogg, tilstand for skjermene, live endring av forhåndsvalg og brytere (ADR-0011) |
| `hub.py` | Fordeling av live-meldinger til skjermene, med begrenset kø per klient |

Antall personer på klar-skjermen velger show-oppsettet med det antallet deltakere fra `site/<studio>/shows/`.
