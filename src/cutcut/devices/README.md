# `cutcut.devices` – utstyr

Klienter mot utstyret. Ingen av dem bestemmer noe; de gjør det motoren har bestemt (I3), og de blokkerer aldri motoren (ADR-0005): kommandoer legges i kø og sendes av en egen tråd med korte tidsavbrudd.

| Modul | Innhold | Plan |
| --- | --- | --- |
| `companion/client.py` | HTTP mot Companion: trykk knapp, custom variables, tilkoblinger, `cutcut_pages_version` | DA-3, DA-9 |
| `companion/executor.py` | Motorens intents → knapper på side 10 og 11. Siste preview vinner (men aldri forbi en TAKE), variabler maks 5/s, kretsbryter (3 feil → 10 s), `S5` reservekutt via `atem-bridge` | DA-3, DA-4, DA-7 |
| `companion/pages.py` | Side 10 og 11 og variablene som `.companionconfig`-filer, laget fra studio-oppsettet (`cutcut companion-pages`, `docs/studio/companion.md`) | DA-9 |
| `atem/bridge.py` | `core` sin side av `atem-bridge`: ATEM-inngang → `C1`, `BIRD`, `LAPTOP` fra show-oppsettet, `AtemReadback` og multiview til sjekkene, direkte kutt og «Kun lyd» som `atem.cmd` (reservevei for Companion, `S5`). Ingen tilbakelesing hvis broen er stille i 3 s (I1) | DA-2 |
| `cameras/base.py` | `CameraDriver` (spes. 7.3, pluss `move_to`/`zoom_to`), `PTZPosition`, `CameraStatus`, `Unsupported` og kommandoene CutCut sender til kameraer | CA-1 |
| `cameras/guarded.py` | `GuardedCamera` pakker hver driver: nekter bevegelse og farge når kameraet er på program eller preview etter ATEM-tilbakelesingen (I2, `PV2`), også rett før sending; uten ATEM nektes alt som beveger. Klemmer til `limits` i `devices.yaml` og logger det (8.4). Én kø per kamera (maks 8, eldste kastes), 200 ms tidsavbrudd, kretsbryter (3 feil → 10 s). En SuperSource-layout på lufta holder alle kameraer i ro | CA-1 |
| `cameras/visca.py` | VISCA over IP (UDP 52381): kommandoene og spørringene fra tabellen i spes. 7.3 som rene funksjoner, svar og feilkoder, 8-byte IP-hodet, og en liten klient som venter på ACK (ikke på at bevegelsen er ferdig) | CA-2 |
| `cameras/visca_ptz.py` | VISCA-delen alle PTZ-kameraer deler: status (strøm, manuell hvitbalanse og eksponering), posisjon, hent og lagre preset med fart, `move_to`, `zoom_to` og små `nudge`-steg. Kameraenheter ↔ grader og zoom 0–1 via `Calibration`, som bekreftes per modell i maskintesten (CA-5) | CA-2, CA-4 |
| `cameras/obsbot.py` | OBSBOT Tail 2: VISCA-delen fra `visca_ptz`, og over OSC: manuell hvitbalanse i kelvin (2000–10000), manuell eksponering (lukkertid «1/50», gain som ISO) og AI-tracking av/på (`SetAiEnable`, Q16) | CA-2, CA-3 |
| `cameras/osc.py` | OSC 1.0 over UDP (int, float, tekst), sendt uten svar; OBSBOT kvitterer ikke for innstillinger | CA-3 |
| `cameras/canon_xc.py` | Canon CR-N300 over VISCA til Canons XC-kommandoliste finnes (Q6): status, posisjon og presets virker; hvitbalanse og eksponering svarer `Unsupported` | CA-4 |
| `cameras/factory.py` | Riktig driver per kamera i `devices.yaml` etter modellnavn; ingen driver for kamera uten IP (fast fugleperspektiv over HDMI) eller modeller som kommer i fase 2 | CA-4 |
| `cameras/service.py` | Alle PTZ-kameraer i `core`: én `GuardedCamera` per kamera med driver, AI-tracking av ved start (`AT6`), posisjon hvert 2. s (kamera som endrer posisjon, er i bevegelse for `S1`; flyttet uten at CutCut ba om det og uten tracking gir `H-CAM-MOVE`), status hvert 10. s (`H-CAM-*`). Nye adresser fra teknikervinduet gir ny driver | CA-6 |
| `pearl/client.py` | REST API v2.0: opptaksstatus, start/stopp per opptaker, lagring, fastvare; Basic-autentisering, passord fra Credential Manager | SE-2 |
| `pearl/recorder.py` | Pearl som opptaker for studioet: start/stopp i kø og idempotent, status hvert 2. s, «starter» holdes til Pearl bekrefter, svarer den ikke avvises start straks; stopper aldri selv (I7) | SE-2, SE-3 |

Kameraene testes mot `cutcut.sim.fake_camera.FakeCamera`, med en egenskapstest der tilfeldige kommandoer og kutt aldri flytter et kamera på lufta. OBSBOT-driveren testes over ekte UDP mot `cutcut.sim.fake_visca`, som svarer med ACK, fullført og feilkoder som et kamera. OSC-siden testes mot `cutcut.sim.fake_osc`. Canon kommer i CA-4.

Testes mot en falsk Companion over ekte HTTP og en falsk Pearl over ekte HTTP (`cutcut.sim.fake_companion`, `cutcut.sim.fake_pearl`, `tests/integration/`). Knappekartet ligger i `site/<studio>/equipment/companion_map.yaml`; side 11 har direkte kutt og «Kun lyd».
