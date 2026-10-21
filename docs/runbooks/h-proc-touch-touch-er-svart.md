# Runbook: Touch er svart

- **Sjekk-ID / regel:** `H-PROC-touch`
- **Alvor:** gul (sendingen og opptaket går)
- **Vises på touch:** nei (det er touch som er borte)
- **Sist testet:** 2026-10-21 med kiosk-vakten i Windows-CI (tørrkjøring), ikke i studio ennå

## Hva brukeren merker

Touch-skjermen er svart, hvit eller står stille. En økt som er i gang, ligger i CutCut og går videre; opptaket på Pearl går videre (I7).

## Hva CutCut gjør selv

Touch sender hjerteslag hvert 5. sekund. Kiosk-vakten ser etter Edge hvert 5. sekund: kjører ikke Edge, startes den, og har touch ikke sendt hjerteslag på 30 s mens CutCut svarer, lukkes Edge og startes på nytt. Økten er uendret.

## Sjekk først (under 2 minutter)

1. Teknikervinduet → **Helse**: er `H-PROC-touch` gul? Svarer resten av CutCut?
2. Er skjermen slått på, og lyser USB-kabelen for berøring?
3. Er kiosk-brukeren logget inn (ser du Windows-skrivebordet eller påloggingsbildet)?

## Løs det

1. Vent 30 s: kiosk-vakten starter Edge på nytt selv.
2. Skjermen av: slå den på.
3. Påloggingsbildet: logg inn som kiosk-brukeren. Automatisk innlogging settes opp med `installer\kiosk\setup-kiosk.ps1 -AutoLogon`.
4. Edge kommer ikke: se loggen `C:\Users\cutcut-kiosk\AppData\Local\CutCut\kiosk-vakt.log`.
5. Bekreft at `H-PROC-touch` er grønn i 30 s.

## Hvis det ikke hjelper

- Brukeren kan starte og stoppe opptak med Stream Deck mens touch er borte.
- Last ned **feilsøkingspakke** (Logg → Feilsøkingspakke) og send den til Magnus Lian, magnus.lian@ntnu.no.

## Bakgrunn

Spesifikasjonen 9.1 («Touch-nettleseren henger»). `docs/studio/kiosk.md`, `installer/kiosk/kiosk-vakt.ps1`.
