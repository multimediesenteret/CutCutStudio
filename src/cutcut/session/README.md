# `cutcut.session` – økter og touch-flyten

Plan: [`docs/plans/session.md`](../../../docs/plans/session.md). Spesifikasjonen 7.5 og 8.1, D-036 og D-043.

| Fil | Innhold |
| --- | --- |
| `manager.py` | `SessionManager`: tilstandsmaskinen hvile → klar → nedtelling → opptak → ferdig. Ren: tid inn, handlinger ut (`PearlStart`, `PearlStop`, `EngineCommand`, `Alert`, `Notice`) |

**Regler som er bygget inn:**

- Én aktiv økt. Nytt kort under opptak avvises; samme kort igjen gjør ingenting.
- Aldri utlogging under nedtelling eller opptak (D-043). Utlogging 30 s etter ferdig opptak, eller etter 3 min uten trykk på klar-skjermen.
- «Starter…» vises til Pearl bekrefter (12.5). Starter ikke Pearl innen 10 s: én setning til brukeren, varsel til tekniker, tilbake til klar.
- Opptak stoppes aldri automatisk (I7). Stopper Pearl av seg selv: rødt varsel med lyd og melding til brukeren.
- Start og stopp kan komme fra touch, tekniker og Stream Deck i hvilken som helst rekkefølge; to trykk er det samme som ett.
- Kun lyd gir modus `A`. Kortnummer kommer aldri inn i modulen, bare brukeren som er slått opp (I8).

Kortleser, kort-API og Pearl-klient kommer i SE-2–SE-5 (M2–M3).
