# Runbook: Etter strømbrudd

- **Sjekk-ID / regel:** alle; morgensjekken
- **Alvor:** rød til alt er oppe igjen
- **Vises på touch:** ja, til lyd, Pearl og ATEM svarer
- **Sist testet:** ikke testet ennå (krever studio og UPS, Q31)

## Hva brukeren merker

Studioet er mørkt, eller touch viser at noe er galt mens utstyret starter. Et opptak som gikk da strømmen forsvant, er stoppet; Pearl lagrer det som var tatt opp.

## Hva CutCut gjør selv

Med UPS slår PC-en seg av ryddig når batteriet er lavt. Med «Power on after AC loss» i BIOS starter PC-en selv når strømmen kommer. Tjenesten CutCut starter med Windows, kiosk-brukeren logges inn og touch åpnes. Supervisor starter `core`, `audio-capture`, `vision` og `atem-bridge`. CutCut kobler seg til utstyret etter hvert som det kommer opp, og morgensjekken kjøres. CutCut starter aldri et opptak selv (I7).

## Sjekk først (under 2 minutter)

1. Vent 5 minutter: ATEM, Pearl og kameraene bruker tid på å starte.
2. Teknikervinduet → **Helse**: hvilke sjekker er fortsatt røde?
3. Er alt utstyret på: ATEM, Pearl, RØDECaster, kameraer, svitsj og skjermer?

## Løs det

1. Slå på det som ikke startet selv (RØDECaster og skjermer gjør ofte ikke det).
2. Startet ikke PC-en: slå den på, og sjekk «Power on after AC loss» i BIOS etterpå (`installer\setup-pc.ps1`, punkt P12).
3. Følg runbooken for hver sjekk som er rød: «Ingen lyd», «Touch er svart», «Opptak startet ikke», «Kamera beveger seg ikke».
4. Sjekk på Pearl at opptaket fra før bruddet finnes.
5. Bekreft at alt i Helse er grønt i 30 s.

## Hvis det ikke hjelper

- Kjør `installer\setup-pc.ps1` og se om noe i Windows-oppsettet er endret.
- Last ned **feilsøkingspakke** (Logg → Feilsøkingspakke) og send den til Magnus Lian, magnus.lian@ntnu.no.

## Bakgrunn

Spesifikasjonen 9.1 og 9.2. `docs/plans/supervisor-ops.md` (strømbrudd), `docs/studio/kiosk.md`, `docs/studio/tjenester.md`.
