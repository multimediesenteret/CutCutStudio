# `cutcut.devices` – utstyr

Klienter mot utstyret. Ingen av dem bestemmer noe; de gjør det motoren har bestemt (I3), og de blokkerer aldri motoren (ADR-0005): kommandoer legges i kø og sendes av en egen tråd med korte tidsavbrudd.

| Modul | Innhold | Plan |
| --- | --- | --- |
| `companion/client.py` | HTTP mot Companion: trykk knapp, custom variables, tilkoblinger, `cutcut_pages_version` | DA-3, DA-9 |
| `companion/executor.py` | Motorens intents → knapper på side 10 og 11. Siste preview vinner (men aldri forbi en TAKE), variabler maks 5/s, kretsbryter (3 feil → 10 s), `S5` reservekutt via `atem-bridge` | DA-3, DA-4, DA-7 |

| `pearl/client.py` | REST API v2.0: opptaksstatus, start/stopp per opptaker, lagring, fastvare; Basic-autentisering, passord fra Credential Manager | SE-2 |
| `pearl/recorder.py` | Pearl som opptaker for studioet: start/stopp i kø og idempotent, status hvert 2. s, «starter» holdes til Pearl bekrefter, svarer den ikke avvises start straks; stopper aldri selv (I7) | SE-2, SE-3 |

Testes mot en falsk Companion over ekte HTTP og en falsk Pearl over ekte HTTP (`cutcut.sim.fake_companion`, `cutcut.sim.fake_pearl`, `tests/integration/`). Knappekartet ligger i `site/<studio>/equipment/companion_map.yaml`; side 11 har direkte kutt og «Kun lyd».
