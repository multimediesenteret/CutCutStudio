# Versjonering og release

## Versjonsnummer

*Semantic Versioning* (`MAJOR.MINOR.PATCH`), tag `vX.Y.Z` på `main`.

| Del | Økes når |
| --- | --- |
| MAJOR | Konfigformat (`schema_version`) eller API endres slik at det krever migrering |
| MINOR | Ny funksjon eller bryter, bakoverkompatibel |
| PATCH | Feilretting uten ny funksjon |

- **Før første release:** `0.x.y`. Milepælene gir `0.1.0` (M1 Simulator), `0.2.0` (M2 Studiotest), `1.0.0` (M3 Grunnmodus i drift). M4-bryterne kommer som `1.x`.
- **Forhåndsversjoner** til studiotest: `vX.Y.Z-rc.N`.
- **Konfig** har egen `schema_version` med migreringsskript (spesifikasjonen 12.3).
- **Spesifikasjonen** har egen versjon (v1, v2 …) i `docs/spec/README.md`.

## Commit-meldinger

*Conventional Commits* gir changelog og neste versjonsnummer:

- `feat(scope): …` → MINOR · `fix(scope): …` → PATCH · `feat!:` eller `BREAKING CHANGE:` i bunnteksten → MAJOR
- `docs`, `test`, `chore`, `ci`, `refactor` gir ingen ny versjon alene.
- Forfatter er alltid `Multimediesenteret <magnus.lian@ntnu.no>`, uten `Co-authored-by` (se `AGENTS.md` 3).

## Sjekkliste for release

Ingen release uten at hvert punkt er krysset av i release-PR-en.

**Dokumentasjon**

- [ ] `CHANGELOG.md`: `[Unreleased]` flyttet til ny versjon med dato
- [ ] `docs/STATUS.md` oppdatert med versjon, hva som er i den, kjente feil
- [ ] `README.md`: kommandoene stemmer (CI kjører dem)
- [ ] `docs/reference/` regenerert (API, konfigskjema, regeltabell, sporbarhet)
- [ ] `src/cutcut/*/README.md` stemmer for endrede moduler
- [ ] `docs/open-questions.md` oppdatert med svar som kom i perioden
- [ ] Nye ADR-er for beslutninger tatt i perioden
- [ ] Runbooks for hendelser i perioden
- [ ] `docs/spec/` eksportert på nytt hvis spesifikasjonen er endret
- [ ] Oppsettsguide (`docs/setup/`) regenerert hvis setup-stegene er endret

**Kvalitet**

- [ ] CI grønn på `main`
- [ ] Simulator-test av hele flyten bestått
- [ ] Maskintester i studio for endrede integrasjoner, rapporter lagt i issues
- [ ] Studiotest for endrede regler eller brytere (skyggemodus når studioet er i drift, D-049)
- [ ] Migrering testet fra forrige versjon sin konfig

**Utrulling** (spesifikasjonen 12.3)

- [ ] Tag `vX.Y.Z` satt av et menneske
- [ ] Windows-pakke, SBOM og sjekksum bygget av CI og lagt på GitHub-releasen
- [ ] Installert i servicevindu ved siden av forrige versjon; `current` byttet
- [ ] Morgensjekk bestått (ellers automatisk tilbakerulling)
- [ ] Simulatoren på Vercel er bygget fra samme versjon

## Branch-regler på GitHub (settes av eier)

- `main` beskyttet: krever pull request, grønn CI og én godkjenning; ingen force-push.
- Tags `v*` kan bare lages av eier.
