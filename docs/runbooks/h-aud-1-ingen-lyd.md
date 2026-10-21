# Runbook: Ingen lyd

- **Sjekk-ID / regel:** `H-AUD-1` og `S4`
- **Alvor:** rød (motoren klipper ikke på lyd)
- **Vises på touch:** ja, som varsel om at noe er galt
- **Sist testet:** 2026-10-21 mot simulatoren (feilen «Lyd borte»), ikke i studio ennå

## Hva brukeren merker

Bildet blir stående på fugleperspektivet, og automatikken står på pause. Opptaket på Pearl går videre (I7), også lyden i opptaket, for den går gjennom RØDECaster og ATEM og ikke gjennom CutCut.

## Hva CutCut gjør selv

Etter 2 s uten lyd kutter motoren til `BIRD` og setter AUTO på pause (`S4`). `audio-capture` prøver å åpne lydkortet på nytt hvert 5. sekund, og supervisor starter prosessen på nytt hvis den har falt. Når lyden er tilbake, går `H-AUD-1` grønn. AUTO slås på igjen av teknikeren.

## Sjekk først (under 2 minutter)

1. Teknikervinduet → **Helse**: står det en grunn ved `H-AUD-1` (for eksempel «fant ikke RODECaster»)?
2. **Helse → Prosesser**: kjører `audio-capture`, eller startes den på nytt hele tiden?
3. Er RØDECaster slått på, og står USB-kabelen til PC-en i?

## Løs det

1. RØDECaster av: slå den på og vent 20 s.
2. USB ut: sett kabelen i samme port igjen. `audio-capture` finner kortet selv innen 5 s.
3. Står grunnen «multitrack»: sett RØDECaster i multitrack-modus (USB 1), se `docs/studio/rodecaster-standardoppsett.md`.
4. Står det at ASIO ikke kan åpnes: lukk andre programmer som bruker RØDECaster. CutCut prøver igjen selv, og bruker WASAPI som reserve.
5. Slå **AUTO** på igjen i teknikervinduet når lyden er tilbake.
6. Bekreft at `H-AUD-1` er grønn i 30 s.

## Hvis det ikke hjelper

- Start tjenesten på nytt: `Stop-Service CutCut`, så `Start-Service CutCut`. Opptaket stoppes ikke.
- Kjør maskintesten `uv run cutcut hwtest audio --site C:\CutCut\site` utenfor sendetid.
- Last ned **feilsøkingspakke** (Logg → Feilsøkingspakke) og send den til Magnus Lian, magnus.lian@ntnu.no.

## Bakgrunn

Spesifikasjonen 5.7 (`S4`), 8.5 (`H-AUD-1`) og 9.1. `docs/research/lyd-fra-rodecaster.md`.
