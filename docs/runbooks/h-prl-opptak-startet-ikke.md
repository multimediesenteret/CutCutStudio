# Runbook: Opptak startet ikke

- **Sjekk-ID / regel:** `H-PRL-1` (startet ikke, Pearl svarer ikke) og `H-PRL-2` (stoppet uten at noen trykket stopp); I7
- **Alvor:** rød
- **Vises på touch:** ja: «Opptaket startet ikke. Teknikeren er varslet.»
- **Sist testet:** 2026-10-21 mot falsk Pearl over HTTP i CI, ikke i studio ennå

## Hva brukeren merker

Etter nedtellingen kommer touch tilbake til klar-skjermen med beskjeden over. Eller opptaket stopper midt i, uten at noen trykket stopp.

## Hva CutCut gjør selv

CutCut ber Pearl starte og venter i 10 s på bekreftelse. Kommer den ikke, går touch tilbake til klar og teknikeren varsles. CutCut starter **aldri** et opptak på nytt selv, og stopper det aldri selv (I7): det må et menneske gjøre.

## Sjekk først (under 2 minutter)

1. Teknikervinduet → **Helse**: hva står ved `H-PRL-1`: svarer ikke, feil eller lite lagring?
2. Se på Pearl foran: lyser opptak? Er det signal på inngangen fra ATEM?
3. **Oppsett → Utstyr**: stemmer Pearls IP-adresse?

## Løs det

1. Lite lagring: flytt eller slett gamle opptak på Pearls nettside.
2. Ingen signal på Pearl: sjekk SDI-kabelen fra ATEM og at ATEM er på.
3. Pearl svarer ikke: slå Pearl av og på, og vent til den har startet helt.
4. Passordet er avvist: sjekk `pearl_password` i Credential Manager (`docs/studio/tjenester.md`).
5. La brukeren trykke **Start** igjen, eller start opptaket på Pearl foran eller med Stream Deck.
6. Bekreft at `H-PRL-1` er grønn i 30 s.

## Hvis det ikke hjelper

- Start opptaket direkte på Pearl, så brukeren ikke mister mer.
- Last ned **feilsøkingspakke** (Logg → Feilsøkingspakke) og send den til Magnus Lian, magnus.lian@ntnu.no.

## Bakgrunn

Spesifikasjonen 7.4, 8.5 (`H-PRL-1`, `H-PRL-2`) og 9.1. Invariant I7 i `AGENTS.md`.
