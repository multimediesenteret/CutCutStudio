# Publisering

CutCut Studio har to slags leveranser som publiseres på hver sin måte.

| Leveranse | Hvor | Hvem bruker den |
| --- | --- | --- |
| Selve appen (motor, skjermer, tjenester) | Windows-pakke på GitHub Releases, installert på regi-PC-en | Studioet |
| Web-simulator: samme skjermer på simulerte data (`docs/simulator.md`) | Vercel (Hobby), bygget fra `main` og pull requests | Multimediesenteret, utviklere, agenter |

Appen kjører **aldri** fra Vercel. Den kjører lokalt i studio (I6), og skjermene serveres av motoren på regi-PC-en.

## Vercel

**Hva publiseres:** web-simulatoren på `/sim/` (forsiden, `/touch` og `/tech` går dit, U-10 godkjent 2026-10-21): de ekte skjermene som spiller av forløp fra den ekte motoren (`docs/simulator.md`). GUI-konseptet ligger som arkiv på `/concept/`.

**Oppsett** (gjøres av eier, ikke av agent):

- Repoet `multimediesenteret/CutCutStudio` er koblet til Vercel-prosjektet `cutcutstudio2026`: gren `main` til produksjon, pull requests til forhåndsvisning.
- Vercel-prosjektet `multimediesenteret/cutcutstudio2026` (https://cutcutstudio2026.vercel.app) bygger fra repo-roten med Framework Preset «Other». Bare `.vercel-out/` publiseres, så resten av repoet (dokumentasjon, utstyrsfiler) kan ikke åpnes fra nettsiden.
- **Bygg (U-9):** `vercel.json` setter alt, så innstillingene i Vercel-prosjektet trenger ikke endres:
  - installering: `pnpm install --frozen-lockfile`
  - bygg: `pnpm --filter "@cutcut/simulator..." run build && node ui/scripts/vercel-out.mjs`
  - ut-mappe: `.vercel-out/` med `concept/` og `sim/`. Ingenting annet fra repoet publiseres.
  - CI-jobben `ui` bygger det samme og tester `/sim/` med Playwright før merge.
- **U-10 (godkjent av eier 2026-10-21, D-053):** forsiden `/`, `/touch`, `/tech` og alle ukjente stier går til simulatoren. `concept/` beholdes som arkiv.
- **Bygg bare når skjermene endres (D-050):** `ignoreCommand` i `vercel.json` kjører `git diff --quiet HEAD^ HEAD -- concept/ ui/ vercel.json package.json pnpm-lock.yaml`. Har siste commit ikke endret noen av dem, hoppes utrullingen over (avslutningskode 0). Ellers, eller hvis forrige commit mangler, bygges det som vanlig. Det sparer utrullinger på Hobby (100 per døgn) når bare dokumentasjon eller Python-kode endres.
- Ingen hemmeligheter eller miljøvariabler med nøkler. Siden er offentlig eller beskyttet med Vercels passord, aldri med Multimediesenteret-data.

**Hobby-planen har to begrensninger som styrer hvordan vi jobber:**

1. *Forfatter må være kontoeier.* Hobby blokkerte utrulling da repoet var privat og commit-forfatteren ikke hadde tilgang til Vercel-prosjektet. Repoet er nå offentlig (D-059), men regelen beholdes så historikken er ryddig og utrullingen aldri stopper av den grunnen. Derfor har alle commits forfatter `Multimediesenteret <magnus.lian@ntnu.no>`, uten `Co-authored-by`-linjer, og CI-jobben `commit-identity` sjekker det. Se `AGENTS.md` 3.
2. *Ikke-kommersiell bruk.* Hobby er for ikke-kommersielle prosjekter. Multimediesenteret bruker det til intern prototyping ved et universitet, uten kommersiell bruk; det holder (Q22, besvart 2026-10-21).

## Windows-pakke

Bygges av CI ved tag `vX.Y.Z` (se `docs/RELEASE.md`): Python, avhengigheter, bygget UI, `atem-bridge`, WinSW-definisjoner, SBOM og sjekksum. Modellfilene (`models/`, etter `models/manifest.yaml`) ligger i pakken, så studio-PC-en ikke trenger nett for dem. Installeres i servicevindu med `installer/install.ps1` (spesifikasjonen 12.3); svarer ikke den nye versjonen på `/api/health`, ruller skriptet tilbake selv.
