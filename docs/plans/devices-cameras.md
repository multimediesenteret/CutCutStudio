# Plan: `devices/cameras` – OBSBOT Tail 2 og Canon CR-N300

Status: godkjent (D-046) · Milepæl: M3 (drivere, presets, grenser) og M4 (AI-tracking, utsnitt, zoom, farge) · Spes. 2.4, 5.13 (`AT`, `F`, `Z`), 7.3, 8.4 steg 4, 8.5 (`H-CAM-*`, `H-CAM-MOVE`); D-005, D-022, D-023; ADR-0005; I2 · Mappe: `src/cutcut/devices/cameras/{base,obsbot,canon_xc}/`

## 1. Formål og avgrensning

Felles `CameraDriver`-grensesnitt (7.3) med to drivere i v1. Grunnmodus trenger bare: status, posisjon (for `S1` og `H-CAM-MOVE`), hent preset off air, og sperre mot bevegelse på PGM/PVW. Resten (AI-tracking, langsom zoom, utsnittsvariasjon, fargejustering) er brytere i M4.

Panasonic og Sony er fase 2 og får bare plass i grensesnittet.

## 2. Grensesnitt

`CameraDriver` som i spes. 7.3, pluss:

```python
class CameraLimits(BaseModel):
    pan: tuple[float, float]; tilt: tuple[float, float]; zoom: tuple[float, float]
    max_speed: float

class GuardedCamera:            # pakker hver driver
    """Avviser bevegelse og farge når kameraet er på PGM eller PVW (I2, PV2),
    klemmer alle verdier til CameraLimits og logger klemmingen (8.4)."""
```

`GuardedCamera` henter PGM/PVW fra ATEM-tilstanden, ikke fra motoren, slik at sperren gjelder også når motoren tar feil. Hver driver har én kø, tidsavbrudd 200 ms og kretsbryter (ADR-0005).

| Driver | Transport | Bygges fra |
| --- | --- | --- |
| `obsbot` | VISCA over IP (UDP 52381) + OSC (UDP 57110/57120) | Tabellene i spes. 7.3 og teknisk referanse; OSC-definisjonene i `site/ntnu-studio/equipment/obsbot/` |
| `canon_xc` | XC over HTTP; VISCA over IP som reserve | XC-kommandolisten fra Canon (Q6). Til den finnes: bare VISCA for preset og posisjon |

## 3. Tilstander og feil

| Situasjon | Gjør |
| --- | --- |
| Kamera svarer ikke (3 tidsavbrudd) | Kretsbryter; kameraets bilder tas ut av utvalget (9.1); gult; videoen går fortsatt via HDMI/SDI |
| Kamera har flyttet seg uten at CutCut ba om det og uten AI-tracking | `H-CAM-MOVE` rødt |
| Kamera ikke i manuell hvitbalanse/eksponering (avvik fra `baseline.yaml`) | `H-CAM-*` gult |
| Kommando utenfor grensene | Klemmes og logges |
| Ved oppstart og slutt på økt | AI-tracking slås av på alle (AT6) |

## 4. Avhengigheter

`python-osc`, egen VISCA-UDP-klient (liten, testet mot byte-tabellene), `httpx`. Utstyr: OBSBOT Tail 2 (antall, Q26), Canon CR-N300, fastvare noteres (Q18).

## 5. Testplan

- VISCA: byte-for-byte mot tabellene; svar og feilkoder parses.
- Falske kameraer i `sim/devices/` som svarer på VISCA, OSC og XC, med treghet og bevegelse.
- I2: egenskapstest der tilfeldige kommandoer sendes mens kameraet er på PGM/PVW → ingen når kameraet.
- Klemming: kommando utenfor grense klemmes og logges (10.4 siste punkt).
- **Maskintester** `tools/hw-test/obsbot.py` og `tools/hw-test/canon.py`: protokoll svarer, presets lagres og hentes, posisjon leses, manuell modus, laveste zoomfart (`Z3`), `SetAiEnable` virker (Q16). Bevegelse bare etter bekreftelse fra tekniker.

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| CA-1 | `CameraDriver`, `GuardedCamera`, grenser, kø | I2-egenskapstest grønn |
| CA-2 | `obsbot` VISCA: status, posisjon, preset | Tester mot falskt kamera |
| CA-3 | `obsbot` OSC: kelvin, eksponering, `SetAiEnable` | Tester mot falskt kamera |
| CA-4 | `canon_xc` med VISCA-reserve | XC når Q6 er besvart |
| CA-5 | Maskintester OBSBOT og Canon | Rapporter i issue |
| CA-6 | `H-CAM-*` og `H-CAM-MOVE` | Vises i helse |
| CA-7 | AI-tracking `AT1`–`AT6` (M4) | Testet alene i studio |

## 7. Åpne spørsmål

- Q6: Canon XC-kommandoliste.
- Q16: virker `SetAiEnable` på studioets fastvare?
- Q26: kamerakart og antall OBSBOT.
- Q19: blandes OBSBOT og Canon i samme show (fargematching)?
