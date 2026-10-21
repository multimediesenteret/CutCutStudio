# Status

Oppdatert: 2026-10-21 · av: Multimediesenteret (agent: Claude)

## Hvor vi er

- **Fase:** M1 Simulator. M0-planene er godkjent (D-046).
- **Milepæl:** M1. Issues ligger i GitHub-milepælen «M1 Simulator».
- **Spesifikasjon:** v1 med endringer fra beslutningsloggen; repoet er fasit (D-040).
- **Vercel:** GUI-konseptet fra `concept/` på https://cutcutstudio2026.vercel.app. Erstattes av web-simulatoren i M1 (U-9, U-10). Utrulling hoppes over når ingen skjermfiler er endret (D-050).

## Ferdig

- Forprosjektet: spesifikasjon, beslutningslogg, ADR-0001–0014, GUI-konsept, overlevering.
- **M0:** planer for alle 13 moduler og milepæler i `docs/plans/`, godkjent med PL-01–PL-08 (D-046). ADR-0012, 0013 og 0014 akseptert.
- Lisens Apache-2.0 (D-047), kontaktperson Magnus Lian (D-048).
- **Ingen skyggerunde (D-049):** M2 heter nå «Studiotest», og motoren klipper live via preview fra første test i studio. Skyggemodus finnes fortsatt i motoren til senere bruk.
- GitHub: milepæler M1–M4, etiketter og issues for M1 (D-050). Issues for M2–M4 opprettes når milepælen starter, så de ikke blir utdaterte.

## Pågår

- M1: første leveranse er C-1 (Python-skjelett og CI).
- NTNU ordner test-PC (Dell SFF, Q28, D-051).

## Kjente feil og funn

- `main` kan ikke beskyttes på gratis privat GitHub. Valgt løsning: agenten pusher aldri til `main`; produkteier merger (D-050).

## Neste steg

1. **Eier:** merge PR #1 (planene) på GitHub.
2. **Agent:** M1 i rekkefølgen C → K → SIM → A → U (se `docs/plans/milestones.md`).
3. **NTNU:** test-PC klar med Windows 11 Pro (Q28); når den er klar: modell, CPU, GPU og om den er NTNU-administrert (Q8, Q20).
