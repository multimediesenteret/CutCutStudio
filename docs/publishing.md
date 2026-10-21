# Publisering

CutCut Studio har to slags leveranser som publiseres på hver sin måte.

| Leveranse | Hvor | Hvem bruker den |
| --- | --- | --- |
| Selve appen (motor, skjermer, tjenester) | Windows-pakke på GitHub Releases, installert på regi-PC-en | Studioet |
| Web-simulator: samme skjermer på simulerte data (`docs/simulator.md`) | Vercel (Hobby), bygget fra `main` og pull requests | NTNU, utviklere, agenter |

Appen kjører **aldri** fra Vercel. Den kjører lokalt i studio (I6), og skjermene serveres av motoren på regi-PC-en.

## Vercel

**Hva publiseres:** web-simulatoren beskrevet i `docs/simulator.md`. Før M1 publiseres den klikkbare prototypen som forside, så oppsettet kan testes.

**Oppsett** (gjøres av eier, ikke av agent):

- Vercel-prosjektet kobles til `multimediesenteret/cutcutstudio`, gren `main` til produksjon, pull requests til forhåndsvisning.
- Byggkommando og ut-mappe settes når simulatoren lages (forslag: `pnpm --filter simulator build`, ut-mappe `ui/apps/simulator/dist/`). Agenten dokumenterer det her når det finnes.
- Ingen hemmeligheter eller miljøvariabler med nøkler. Siden er offentlig eller beskyttet med Vercels passord, aldri med NTNU-data.

**Hobby-planen har to begrensninger som styrer hvordan vi jobber:**

1. *Forfatter må være kontoeier.* Hobby blokkerer utrulling fra private repoer når commit-forfatteren ikke har tilgang til Vercel-prosjektet («does not support collaboration for private repositories»). Derfor har alle commits forfatter `Multimediesenteret <magnus.lian@ntnu.no>`, uten `Co-authored-by`-linjer, og CI-jobben `commit-identity` sjekker det. Se `AGENTS.md` 3.
2. *Ikke-kommersiell bruk.* Hobby er for ikke-kommersielle prosjekter. NTNU bruker det til intern prototyping ved et universitet, uten kommersiell bruk; det holder (Q22, besvart 2026-10-21).

## Windows-pakke

Bygges av CI ved tag `vX.Y.Z` (se `docs/RELEASE.md`): Python, avhengigheter, bygget UI, `atem-bridge`, WinSW-definisjoner, SBOM og sjekksum. Modellfiler lastes ned ved installasjon etter `models/manifest.yaml`. Installeres i servicevindu etter spesifikasjonen 12.3, med automatisk tilbakerulling hvis morgensjekken feiler.
