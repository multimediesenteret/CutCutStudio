# `cutcut.supervisor` – holder studioets prosesser i gang

Egen liten prosess (SO-1, spesifikasjonen 9.1, `docs/plans/supervisor-ops.md`). Den starter `core`, `atem-bridge` og `audio-capture`. Når en prosess faller ut, starter den den på nytt. Den kjenner ingen regler, bare prosesser.

| Fil | Innhold |
| --- | --- |
| `supervisor.py` | `ProcessSpec` og `Supervisor.step()`: omstart med pause 1, 2, 5, 10 og 30 s (tilbake til 1 s etter 60 s god drift), helsesjekk (3 feil på rad = henger → stopp og start), telling av omstarter siste 10 min |
| `orphans.py` | Barna dør med supervisor, uansett hvordan den slutter: Job Object på Windows, `PR_SET_PDEATHSIG` på Linux. Ellers ville en foreldreløs `core` holde port 8080, og hver nye `core` ville feile |
| `report.py` | `supervisor.status` på bussen hvert 2. sekund. `core` viser det under Helse og gir `H-PROC-<prosess>` |
| `main.py` | `cutcut supervisor`: prosesslisten, helsesjekk av `core` (`/api/health`) og ATEM-adressen. Adressen leses på nytt før hver start av `atem-bridge`, med adresser lagret i teknikervinduet. I Windows-pakken brukes pakkens egen Node (`node\node.exe`) |

```bash
uv run cutcut supervisor --site site/multimediesenteret --data data
uv run cutcut supervisor --site site/example --data data --audio-wav opptak.wav   # lyd fra fil til AU-5
```

`H-PROC-<prosess>` er gult (spesifikasjonen 8.5). Det gis når en prosess er nede og startes på nytt, og når den er startet på nytt mer enn 5 ganger på 10 minutter. Varselet gis på nytt når prosessen kjører igjen. Status eldre enn 10 s betyr at supervisor selv er borte.

Tester (`tests/unit/supervisor/`) bruker ekte barneprosesser:
- dreper et barn og sjekker omstart og pauser;
- lar et barn henge og sjekker at det blir drept;
- dreper supervisor hardt og sjekker at barna dør.

De kjøres på Linux og Windows i CI. Tjenesten (WinSW) kommer i SO-2.
