# Status

Oppdatert: 2026-10-23 · av: Multimediesenteret (agent: Claude)

## Kort fortalt

Alt i CutCut som kan bygges og testes uten studio, er bygget og testet i CI mot simulatoren og falske enheter. Det som står igjen, krever studioet: maskintester på ekte utstyr, kalibrering, og prøving av grunnmodus og hver bryter. Det gjøres i én studioperiode etter sjekklista i [`docs/studio/testdag.md`](studio/testdag.md) (D-066).

## Hvor vi er

- **Versjon:** `0.1.0` (2026-10-22), første release med Windows-pakke på GitHub. Endringer: `CHANGELOG.md`.
- **Fase:** klar for studioperioden. Plan og rekkefølge for arbeidet før perioden: [`docs/plans/for-studio.md`](plans/for-studio.md) (P1–P9, alle ferdige).
- **Milepæler:** M0 og M1 er ferdige. M2 (studiotest), M3 (grunnmodus i drift) og M4 (brytere) er bygget; de lukkes når studioprøvene i `testdag.md` er gjort og rapportert i issuene.
- **Spesifikasjon:** v1 med endringer fra beslutningsloggen (D-001–D-072); repoet er fasit (D-040).
- **Vercel:** web-simulatoren er forsiden på https://cutcutstudio2026.vercel.app; konseptet ligger som arkiv på `/concept/`.

## Hva som er bygget

| Del | Innhold | Plan |
| --- | --- | --- |
| Grunnmur | Modeller, konfig, klokke, logging, SQLite, ZeroMQ-buss, plattform-adaptere | `common.md` |
| Regimotor | Grunnmodus (`T`, `PV`, `K`, `H`, `S`, `B`, `CT`, overstyring), skyggemodus per bryter, og bryterreglene `L`, `F`, `Z`, `AT`, `V`, `R` | `core.md`, `features.md` |
| Lyd | `audio-capture` med ASIO/WASAPI, VAD, frasegrenser, lekkasje, dempet mic (`S6`), mic-sjekk | `audio.md` |
| Utstyr | Companion (preview + TAKE, `S5` reservekutt), `atem-bridge`, ISO-opptak, Pearl, PTZ-kameraer (OBSBOT over VISCA og OSC, Canon over VISCA) med kameravakt (I2) | `devices-*.md` |
| Videolag | Multiview fra INOGENI eller ATEM-ens USB-C, valgt i oppsettet og funnet på navnet (D-071), forsinkelsen tatt hensyn til i motoren, rutekart (også fra bildet), content, bevegelse, programbekreftelse, kamerabilder, ansikt og munn (YuNet på CPU) | `vision.md` |
| Økt og skjermer | Touch med Start-knapp («Gjest»), teknikervindu med roller, show-typer, «Kun lyd», web-simulator | `session.md`, `ui.md` |
| Oppsett og helse | Setup-hjelperen med ti steg (rutekart, mikrofonfasit, fargematching), helsekatalogen, morgensjekk, varsling (av), support-e-post | `setup-health.md` |
| Drift | Supervisor, Windows-tjeneste, kiosk, `setup-pc.ps1`, pakke med tilbakerulling, nattlig backup, runbooks, 72-timerstest (`cutcut hwtest soak`) | `supervisor-ops.md` |
| Maskintester og akseptanse | `cutcut hwtest audio · atem · camera · vision · pearl · faces · soak · akseptanse` | `docs/studio/maskintest.md` |
| Forbedringer P10–P14 (D-072) | Grafikk på lufta respekteres og ingen blind TAKE uten ATEM (P10); `cutcut opptak importer` for opptak til justering (P11); plassjekk (P12, skygge); lyd som tilpasser seg økten (P13, skygge); «Sjekk dagens oppsett» (P14) | `p10-p14.md` |
| Feilsøkingsmodus | Under Helse: tar opp alt som kommer inn til motoren i 1–72 timer (`data\debug`), for studioperioden og feilsøking | `docs/studio/maskintest.md` |

Manual for oppsett og drift: [`docs/manual/`](manual/README.md) (PDF ved siden av, `pnpm manual`). Hvordan det henger sammen: [`docs/architecture/`](architecture/README.md). Hva som er endret for brukeren: `CHANGELOG.md` under `[Unreleased]`.

## Åpne GitHub-issues

Alle åpne issues gjelder enten studioprøver eller ting som er utsatt med vilje:

- **Studioperioden** (bygget, venter på ekte utstyr): AU-5, AU-7, DA-5, DA-6, DA-8, DA-9, HS-2, HS-6, HS-7, VI-4, CA-4, CA-5, SO-2, SO-5, SO-6, SO-7, SO-8, SO-9, T-M2, T-M3, og bryterne P3–P8 (#178–#183). P9 (#184) venter på gjennomlesing av eier.
- **Etter studioperioden:** SIM-8 (trenger opptak, Q1), SIM-4, kortleser og kort-API (SE-4, SE-5), e-postvarsling (HS-3, Q40), Panopto (Q5).

## Kjente funn og begrensninger

- Studioets mikser er ATEM Television Studio HD8 ISO, ikke Mini Extreme ISO som spesifikasjonen 2.2 er skrevet for (D-053). Det påvirker oppsett og rutekart, ikke motoren.
- Canon CR-N300 styres over VISCA til Canons XC-kommandoliste finnes (Q6): posisjon og presets virker, hvitbalanse og eksponering ikke.
- `V6` (blikkretning) og `H-AUD-2` (støy i stillhet) er ikke bygget.
- Grenseverdiene i reglene og i ansiktsanalysen er startpunkter. De justeres mot opptakene fra studioperioden (Q1, Q2).
- Den lokale Playwright-testen `simulator.spec.ts` kan feile av og til på trege maskiner; i CI er den grønn.

## Neste steg

1. **Eier:** les gjennom sjekklista `docs/studio/testdag.md` (P9, #184), og book studioperioden. Planen `docs/plans/p10-p14.md` er bygget (D-072); plassjekken og lydtilpasningen står i skygge og prøves i perioden (testdag 5.7 og 5.8).
2. **Studioperioden:** følg `testdag.md` punkt for punkt; lim rapportene inn i issuene.
3. **Agent, etter perioden:** juster grenseverdier mot opptakene (Q1, Q2), bygg SIM-8 (avspilling av ekte forløp), og lukk M2–M4 når rapportene er godkjent.
4. **Senere utvidelser:** `docs/plans/for-studio.md` 6 (DeckLink som capture, statuslys i rommet (Busylight, Q42), teksting etter opptak, `V6`, tyngre taler-modell, web-simulator trinn 2), og kortinnlogging, e-postvarsling og Panopto.
