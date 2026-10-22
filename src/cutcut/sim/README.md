# `cutcut.sim` – simulatoren

Kjører den ekte motoren og skallet mot syntetiske talere og falske enheter, uten utstyr. Plan: [`docs/plans/sim.md`](../../../docs/plans/sim.md).

| Fil | Innhold |
| --- | --- |
| `voices.py` | Syntetiske talere som lager de samme målingene som `audio-capture` (`MicFrame`): manus eller en stokastisk samtale med frø (turbytter, fraser og pauser, overlapp, «mm», latter, lekkasje) |
| `fakes.py` | Falske enheter i prosessen: ATEM via Companion (preview, TAKE, direkte kutt, operatør som kutter selv), Pearl (asynkron start, feil), kortleser og kort-API med fiktive testkort |
| `vision.py` | Tegnet videolag til `cutcut sim --vision`: multiviewen følger falsk ATEM (program, preview, panorering) og går gjennom den samme koden som `cutcut vision`, så teknikervinduet viser utsnitt (D-056) og Helse viser `H-VID-1`/`H-VID-3` |
| `fake_camera.py` | Falskt PTZ-kamera i prosessen (`CameraDriver`) som husker hver kommando som nådde det, så testene kan vise at ingenting når et kamera på lufta (I2) |
| `fake_visca.py` | Falsk OBSBOT over ekte UDP som snakker VISCA over IP: presets, posisjon, zoom og moduser, med ACK, fullført og syntaksfeil som et ekte kamera. Kan tie helt (kamera borte fra nettet) |
| `fake_osc.py` | OSC-siden av den falske OBSBOT-en over ekte UDP: kelvin, eksponering og AI-tracking havner i samme `FakeCamera` |
| `scenario.py` | Scenarioformatet i `sim/scenarios/*.yaml`: manus, feil og forventninger |
| `simulation.py` | `Simulation` (motor + skall + talere + falske enheter på falsk klokke) og `run_scenario()` |

**Scenarioer** (`sim/scenarios/`): monolog, samtale, panel med 3 og 4, krysstale, stillhet, laptop med slide og med video, vertens innskudd, dempet mic, og feil (lyd borte, kamera i bevegelse, Companion nede, operatør kutter på ATEM). Alle kjøres som tester; de stokastiske samtalene sjekker også akseptansekriteriene i 10.4 som kan måles uten utstyr (`K1`/`K2` ≥ 90 %, preview ≥ 300 ms i ≥ 95 %).

**Falske enheter over nett** (HTTP for Companion og Pearl, VISCA/OSC for kameraer) lages sammen med de ekte klientene i M2 og bruker tilstandsmaskinene her.
