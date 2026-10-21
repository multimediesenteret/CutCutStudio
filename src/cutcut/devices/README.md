# `cutcut.devices` – utstyr

Klienter mot utstyret. Ingen av dem bestemmer noe; de gjør det motoren har bestemt (I3), og de blokkerer aldri motoren (ADR-0005): kommandoer legges i kø og sendes av en egen tråd med korte tidsavbrudd.

| Modul | Innhold | Plan |
| --- | --- | --- |
| `companion/client.py` | HTTP mot Companion: trykk knapp, custom variables, tilkoblinger, `cutcut_pages_version` | DA-3, DA-9 |
| `companion/executor.py` | Motorens intents → knapper på side 10 og 11. Siste preview vinner (men aldri forbi en TAKE), variabler maks 5/s, kretsbryter (3 feil → 10 s), `S5` reservekutt via `atem-bridge` | DA-3, DA-4, DA-7 |

Testes mot en falsk Companion over ekte HTTP (`cutcut.sim.fake_companion`, `tests/integration/`). Knappekartet ligger i `site/<studio>/equipment/companion_map.yaml`; side 11 har direkte kutt og «Kun lyd».
