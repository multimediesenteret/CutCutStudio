# Status

Oppdatert: 2026-10-22 · av: Multimediesenteret (agent: Claude)

## Hvor vi er

- **Fase:** alt som kan lages uten studio, lages før studioperioden (D-066). Plan og rekkefølge: `docs/plans/for-studio.md` (P1–P9). P1 (DeckLink, nett, support-e-post) er gjort. M2 og M3 er bygget; det som står igjen der, prøves i studioperioden.
- **Milepæl:** M4 «Brytere» (issues P1–P9 og F-1–F-11), med M2 og M3 åpne til studioprøvene er gjort.
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
- M2: følgende er merget og testet mot falske enheter i CI:
  - `cutcut core` med Companion, Pearl og atem-bridge;
  - `audio-capture` (AU-1, AU-2);
  - multiview-sjekken (D-055, D-056);
  - supervisor (SO-1).

  Maskintester på test-PC og i studio gjenstår.
- M2 videre (merget, testet mot falske enheter og i Windows-CI):
  - lyd: frasegrenser, lekkasje og S6, ASIO/WASAPI, lydsjekk og mic-sjekk (AU-3–AU-7);
  - helse og morgensjekk (HS-1, HS-2, HS-4);
  - Companion-sider og makrosjekk (DA-7, DA-9);
  - maskintester (`cutcut hwtest audio|atem`);
  - Windows-tjeneste, kiosk og `setup-pc.ps1` (SO-2, SO-5, SO-6).

  Resten av M2 venter på test-PC og studio. Rekkefølgen står i `docs/studio/testdag.md`.
- M3 (påbegynt): videolaget `cutcut vision` med ruter, content-deteksjon og bevegelse/programbekreftelse (VI-1–VI-3), kamerabilder i teknikervinduet (D-056) kameravakten `GuardedCamera` (CA-1) OBSBOT over VISCA og OSC (CA-2, CA-3) Canon over VISCA (CA-4, XC venter på Q6) kamerahelse i `core` (CA-6) maskintestene `cutcut hwtest camera` og `cutcut hwtest vision` (CA-5, VI-4) nattlig vedlikehold med kopi av databasen (SO-7) runbooks for tekniker (SO-9) varsel på e-post (HS-3, av til det er testet; SMTP-relé venter på Q40), Windows-pakke med `install.ps1` og tilbakerulling (SO-3, SO-4), oppsett som lagres og hentes i appen (D-060), resten av helsekatalogen for grunnmodus (HS-7), show-typer med «Kun lyd» og Panopto som forberedt (SE-6, SE-7), setup-hjelperen med ti steg, sjekk, godkjenning og «Fiks for meg» for ATEM-navnene (HS-5, HS-6; hvert steg gjenstår å prøve i studio med tekniker), rutekartet fra bildet med hjørner som kan dras (VI-5), og ISO-opptak i ATEM fra Opptak eller med Pearl (DA-8). Prøves uten utstyr med `cutcut sim --vision`.
- Innlogging (D-057): studioet bruker Start-knappen («Gjest») til appen har vært testet en stund. Kortleser og kort-API (SE-4, SE-5) er flyttet til M4.
- Multimediesenteret ordner test-PC (Dell SFF, Q28, D-051).

## Kjente feil og funn

- Studioets mikser er ATEM Television Studio HD8 ISO (SDI), ikke Mini Extreme ISO (D-053). Påvirker studio-oppsett, Companion og rutekart, ikke motoren. Inngangskartet er bekreftet og lagt inn i `site/multimediesenteret/` (D-054). IP-adresser settes i teknikervinduet, og multiviewen sjekkes automatisk (D-055).

- `main` kan ikke beskyttes på gratis privat GitHub. Valgt løsning: agenten pusher aldri direkte til `main`, men merger egne pull requests når CI er grønn (D-050, D-052).

## Neste steg

1. **Agent:** M1 i rekkefølgen C → K → SIM → A → U (se `docs/plans/milestones.md`).
2. **Multimediesenteret:** test-PC klar med Windows 11 Pro (Q28); når den er klar: modell, CPU, GPU og om den er sentralt administrert (Q8, Q20).
