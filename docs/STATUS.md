# Status

Oppdatert: 2026-10-21 · av: Multimediesenteret (agent: Claude)

## Hvor vi er

- **Fase:** M1 Simulator. M0-planene er godkjent (D-046).
- **Milepæl:** M1. Issues ligger i GitHub-milepælen «M1 Simulator».
- **Spesifikasjon:** v1 med endringer fra beslutningsloggen; repoet er fasit (D-040).
- **Vercel:** web-simulatoren er forsiden på https://cutcutstudio2026.vercel.app (U-9, U-10). Konseptet ligger som arkiv på `/concept/`. Utrulling hoppes over når ingen skjermfiler er endret (D-050).

## Ferdig

- Forprosjektet: spesifikasjon, beslutningslogg, ADR-0001–0014, GUI-konsept, overlevering.
- **M0:** planer for alle 13 moduler og milepæler i `docs/plans/`, godkjent med PL-01–PL-08 (D-046). ADR-0012, 0013 og 0014 akseptert.
- Lisens Apache-2.0 (D-047), kontaktperson Magnus Lian (D-048).
- **Ingen skyggerunde (D-049):** M2 heter nå «Studiotest», og motoren klipper live via preview fra første test i studio. Skyggemodus finnes fortsatt i motoren til senere bruk.
- GitHub: milepæler M1–M4, etiketter og issues for M1 (D-050). Issues for M2–M4 opprettes når milepælen starter, så de ikke blir utdaterte.

## Pågår

- M1: grunnmuren (C-1–C-8), regimotoren (K-1–K-10), simulatoren (SIM-1, -2, -5, -6: `uv run cutcut sim`), økt (SE-1) og API (A-1–A-5) er merget. Skjermene: arbeidsområde (U-1), komponenter (U-2), klient (U-3) touch-skjermen (U-4, U-5) og teknikervinduet (U-6–U-8) er ferdige og testes ende til ende mot simulatoren i CI. Web-simulatoren (U-9) ligger på `/sim/`. Eksport (A-6) og arkitekturdokumentasjon (D-1) er ferdige. U-10 er gjort: forsiden på Vercel er simulatoren. M1 er ferdig; SIM-3/SIM-4 (falske nettverksenheter) er flyttet til M2. Versjonstagg venter (ikke viktig ennå, D-053).
- NTNU ordner test-PC (Dell SFF, Q28, D-051).

## Kjente feil og funn

- Studioets mikser er ATEM Television Studio HD8 ISO (SDI), ikke Mini Extreme ISO (D-053). Påvirker studio-oppsett, Companion og rutekart, ikke motoren. Inngangskartet er bekreftet og lagt inn i `site/ntnu-studio/` (D-054). IP-adresser settes i teknikervinduet, og multiviewen sjekkes automatisk (D-055).

- `main` kan ikke beskyttes på gratis privat GitHub. Valgt løsning: agenten pusher aldri direkte til `main`, men merger egne pull requests når CI er grønn (D-050, D-052).

## Neste steg

1. **Agent:** M1 i rekkefølgen C → K → SIM → A → U (se `docs/plans/milestones.md`).
2. **NTNU:** test-PC klar med Windows 11 Pro (Q28); når den er klar: modell, CPU, GPU og om den er NTNU-administrert (Q8, Q20).
