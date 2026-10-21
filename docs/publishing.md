# Publisering

CutCut Studio har to slags leveranser som publiseres på hver sin måte.

| Leveranse | Hvor | Hvem bruker den |
| --- | --- | --- |
| Selve appen (motor, skjermer, tjenester) | Windows-pakke på GitHub Releases, installert på regi-PC-en | Studioet |
| Dokumentasjon, prototype og UI-demo mot simulator | Vercel (Hobby), bygget fra `main` | Utviklere, agenter, NTNU |

Appen kjører **aldri** fra Vercel. Den kjører lokalt i studio (I6), og skjermene serveres av motoren på regi-PC-en.

## Vercel

**Hva publiseres:** en statisk side med

- dokumentasjonen (`docs/`, gjort om til nettsider),
- den klikkbare prototypen (`docs/prototype/`),
- fra M1: `touch`- og `tech`-skjermene bygget mot en simulert motor i nettleseren, så man kan prøve flyten uten studio.

**Oppsett** (gjøres av eier, ikke av agent):

- Vercel-prosjektet kobles til `multimediesenteret/cutcutstudio`, gren `main` til produksjon, pull requests til forhåndsvisning.
- Byggkommando og ut-mappe settes når docs-siden lages (forslag: `pnpm --filter docs build`, ut-mappe `site-dist/`). Agenten dokumenterer det her når det finnes.
- Ingen hemmeligheter eller miljøvariabler med nøkler. Siden er offentlig eller beskyttet med Vercels passord, aldri med NTNU-data.

**Hobby-planen har to begrensninger som styrer hvordan vi jobber:**

1. *Forfatter må være kontoeier.* Hobby blokkerer utrulling fra private repoer når commit-forfatteren ikke har tilgang til Vercel-prosjektet («does not support collaboration for private repositories»). Derfor har alle commits forfatter `Multimediesenteret <magnus.lian@ntnu.no>`, uten `Co-authored-by`-linjer, og CI-jobben `commit-identity` sjekker det. Se `AGENTS.md` 3.
2. *Ikke-kommersiell, personlig bruk.* Hobby er etter Vercels vilkår for personlige, ikke-kommersielle prosjekter. Om NTNU-bruk passer innenfor, eller om prosjektet bør flyttes til Pro eller annen hosting (for eksempel GitHub Pages), er Q22 i `docs/open-questions.md`.

## Windows-pakke

Bygges av CI ved tag `vX.Y.Z` (se `docs/RELEASE.md`): Python, avhengigheter, bygget UI, `atem-bridge`, WinSW-definisjoner, SBOM og sjekksum. Modellfiler lastes ned ved installasjon etter `models/manifest.yaml`. Installeres i servicevindu etter spesifikasjonen 12.3, med automatisk tilbakerulling hvis morgensjekken feiler.
