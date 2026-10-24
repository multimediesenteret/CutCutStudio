# `cutcut.recordings` – opptak til justering (P11)

Setter opptakene fra studioperioden sammen til avspillingspakker, så reglene kan justeres mot ekte samtaler (Q1, Q2), avspilling i simulatoren kan bygges (SIM-8), og lydtilpasningen (P13) kan prøves. Plan: `docs/plans/p10-p14.md` 3. Beslutning: D-072.

**CutCut tar ikke opp lyd selv.** RØDECaster-en tar opp hver mikrofon til eget kort, ATEM-en tar ISO-opptak, og feilsøkingsmodus logger `level_db` per mikrofon hvert 10. ms. Importen finner hvor hver WAV-fil hører hjemme i tid ved å sammenligne lydnivået med loggen (krysskorrelasjon av nivåkurvene, så korrelasjon på de beste kandidatene). Det trengs verken klapp eller tidskode.

| Fil | Ansvar |
| --- | --- |
| `wav.py` | Leser WAV (PCM 16/24/32 bit, 32 bit flyttall, flere kanaler i én fil) uten å lese hele filen: nivå per 10 ms, 30 s om gangen |
| `importer.py` | `load_levels` (fra feilsøkingsopptaket), `align`, `place`, `check`, `write_package`, `expired`; kommandoene |

**Kommandoer:**

```powershell
uv run cutcut opptak importer --episode 2026-11-04-a --samtykke --out D:\opptak `
  --wav M1=E:\REC0001\mic1.wav --wav M2=E:\REC0001\mic2.wav
uv run cutcut opptak rydd --out D:\opptak --ja
```

`--wav M2=multitrack.wav:3` tar kanal 3 fra en fil med flere kanaler. Uten `--samtykke` stopper importen (D-072). En pakke skrives aldri over.

**Pakken** (`<out>/<episode>/`): `meta.yaml` (når hver fil starter, hvor sikker matchen er, samtykke, slettedato om 12 måneder), `mic/` (filene som de ble tatt opp), `measures.jsonl.gz` (feilsøkingsopptaket for samme tid) og `decisions.jsonl` (beslutningene fra databasen). Pakkene inneholder stemmer og hører aldri hjemme i git.

**Advarsler:** match under 0,6 (feil fil for mikrofonen?), og filer fra samme opptak som starter mer enn 40 ms fra hverandre.

**Tester:** `tests/unit/recordings/` med syntetisk tale: filene plasseres på 10 ms, byttede filer oppdages, samtykke kreves, utgåtte pakker finnes.
