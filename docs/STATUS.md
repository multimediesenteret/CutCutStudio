# Status

Oppdatert: 2026-10-21 · av: Multimediesenteret (agent: Claude)

## Hvor vi er

- **Fase:** M0 Planer. Implementasjonsplanene er skrevet og venter på godkjenning. Ingen produksjonskode ennå.
- **Milepæl:** M0, pull request fra grenen `agent/m0-plans`.
- **Spesifikasjon:** v1, 20.10.2026 (`docs/spec/`); repoet er fasit (D-040).
- **Vercel:** GUI-konseptet fra `concept/` på https://cutcutstudio2026.vercel.app. Erstattes av web-simulatoren i M1 (U-9, U-10).

## Ferdig

- Forprosjektet: spesifikasjon, beslutningslogg D-001–D-045, ADR-0001–0014, GUI-konsept, overlevering.
- **M0:** planer for alle 13 moduler og milepæler i `docs/plans/` (oversikt i `docs/plans/README.md`). Planene foreslår PL-01–PL-08, blant annet at ADR-0012 (`atem-bridge`), ADR-0013 (web-simulator) og ADR-0014 (`audio-capture`, presisert til å sende målinger, ikke rå lyd) bekreftes.
- Nye spørsmål Q27–Q36 i `docs/open-questions.md`.

## Pågår

- Produkteier vurderer planene.
- NTNU samler inn det som står i `docs/open-questions.md` og `docs/intake/`.

## Kjente feil og funn

- **`main` kan ikke beskyttes:** repoet er privat på gratis GitHub, og da er branch protection ikke tilgjengelig (API-et svarer 403). Overleveringen forutsetter beskyttelse. Alternativer i `docs/plans/milestones.md`, spørsmål Q27. Til det er avgjort pusher agenten aldri til `main`.

## Neste steg

1. **Eier:** les og godkjenn planene (PR `agent/m0-plans`). Svar på Q11 (lisens), Q12 (kontakter), Q27 (GitHub/Vercel), Q36 (PL-01–PL-08). Si om issues og milepæler skal opprettes i GitHub.
2. **Agent etter godkjenning:** før godkjente PL-er inn i beslutningsloggen og sett ADR-0012–0014 til «Akseptert»; opprett issues; start M1 med C-1 (Python-skjelett og CI).
3. **NTNU:** opptak og klippeliste (Q1–Q2), studioinventar, Windows-testmaskin (Q28), servicevindu (Q30), strøm (Q31).
</content>
</invoke>
