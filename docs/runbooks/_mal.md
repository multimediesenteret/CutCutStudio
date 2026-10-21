# Runbook: <kort navn på problemet>

<!-- Mal for runbooks. Kopier til docs/runbooks/<sjekk-id>-<kort-navn>.md, f.eks.
     h-aud-1-ingen-lyd.md. Skriv for en tekniker som står i studio uten å kjenne koden.
     Korte setninger. Ett tiltak per punkt. -->

- **Sjekk-ID / regel:** `H-XXX-n` (og regel-ID hvis motoren reagerer, f.eks. `S4`)
- **Alvor:** rød (stopper grunnmodus) / gul (avvik, sendingen går)
- **Vises på touch:** ja, med teksten «…» / nei
- **Sist testet:** ÅÅÅÅ-MM-DD av <navn>, mot simulator / i studio

## Hva brukeren merker

Én eller to setninger. Hva ser de på touch, og hva skjer med opptaket?

## Hva CutCut gjør selv

Hva motoren og supervisor gjør automatisk (fallback, omstart, varsel), og hvor lenge det tar. Husk: sendingen og opptaket går videre uten CutCut (I1), og opptak stoppes aldri automatisk (I7).

## Sjekk først (under 2 minutter)

1. Se teknikervinduet → **Helse**: hvilke sjekker er røde?
2. …
3. …

## Løs det

1. …
2. …
3. Bekreft at sjekken er grønn i 30 s.

## Hvis det ikke hjelper

- Last ned **feilsøkingspakke** (Logg → Feilsøkingspakke) og send den til <kontakt>.
- Kontakt: Magnus Lian, magnus.lian@ntnu.no.

## Bakgrunn

Lenker til spesifikasjonen, ADR, plan eller utstyrsdokumentasjon (`docs/studio/`).
