# Overlevering til utviklingsagenten

Dato: 2026-10-21 · Fra: forprosjektet (Magnus Lian med Claude) · Til: AI-agent som skal bygge CutCut Studio

Forprosjektet er ferdig. Alt som er avtalt ligger i repoet. Denne siden sier hva eieren gjør før agenten slippes til, hva agenten skal starte med, og hva som fortsatt mangler.

## 1. Eieren gjør dette først

| # | Hva | Hvor | Hvorfor |
| --- | --- | --- | --- |
| 1 | Beskytt `main`: krev pull request, grønn CI og én godkjenning; ingen force-push | GitHub → Settings → Branches | Agenten merger aldri selv (`AGENTS.md` 7) |
| 2 | Gi agenten tilgang til repoet (skrive til grener, ikke admin) | GitHub-appen for agenten | |
| 3 | Sjekk at agentens commits får forfatter `Multimediesenteret <magnus.lian@ntnu.no>` og ingen `Co-authored-by` | `.claude/settings.json`, `tools/setup-git.sh`, CI `commit-identity` | Vercel Hobby blokkerer andre forfattere |
| 4 | Lag milepælene M0–M4 i GitHub (eller la agenten foreslå dem) | GitHub → Issues → Milestones | Planene knyttes til dem |
| 5 | Svar på Q11 (lisens) og Q12 (kontaktpersoner) | `docs/open-questions.md` | Trengs før M1, ikke før M0 |

## 2. Startmelding til agenten

Lim inn dette som første oppgave:

> Du skal bygge CutCut Studio. Les `AGENTS.md` først og følg den. Repoet er ferdig forprosjekt uten kode. Din første oppgave er milepæl M0: lag implementasjonsplaner i `docs/plans/<modul>.md` etter malen i spesifikasjonens 0.4 for alle moduler i rekkefølgen fra spesifikasjonens seksjon 11, og `docs/plans/milestones.md` med forslag til GitHub-issues for M0–M4. Ta hensyn til beslutningsloggen (`docs/forprosjekt/beslutningslogg.md`, nyere rader går foran spesifikasjonen), ADR-0012–0014 som er forslag du skal bekrefte eller avvise i planene, GUI-konseptet i `concept/` og `docs/design/`, og ytelseskravene i `docs/design/gui-konsept.md`. Skriv ingen produksjonskode. Jobb på grenen `agent/m0-plans`, lever én pull request, oppdater `docs/STATUS.md`, og legg nye spørsmål i `docs/open-questions.md`.

## 3. Hva agenten har, og hva den ikke har

| Har | Har ikke (ennå) |
| --- | --- |
| Full spesifikasjon, beslutningslogg D-001–D-040, ADR-0001–0014 | Ekte opptak og klippeliste (Q1–Q2) – trengs til M2 |
| Teknisk referanse med protokoller for ATEM, Companion, OBSBOT (VISCA + OSC), Pearl, Canon, Panasonic, Sony | Canon XC-kommandoliste (Q6) |
| Standardoppsett for RØDECaster, deltakerfarger, GUI-konsept med ytelseskrav | NTNU-API-nøkkel og svarformat (Q4), Panopto-flyt (Q5) |
| Klikkbart konsept på https://cutcutstudio2026.vercel.app | Tilgang til utstyret (alt testes mot simulator; maskintester kjøres av tekniker) |
| OBSBOT OSC-definisjoner i `site/ntnu-studio/equipment/obsbot/` | Utfylt studioinventar med IP-er og fastvare (Q18) |

## 4. Hva som blokkerer hva

| Milepæl | Kan starte når | Åpne spørsmål som må være besvart før milepælen er *ferdig* |
| --- | --- | --- |
| M0 Planer | Nå | Ingen. Spørsmål legges i planene |
| M1 Simulator | M0 godkjent, Q11 og Q12 besvart | Q21 avgjør lyd-adapteren, men simulatoren trenger den ikke |
| M2 Skyggemodus i studio | M1 ferdig | Q1, Q2, Q3, Q7, Q8, Q9, Q13, Q14, Q18, Q20, Q21, Q24, Q26 |
| M3 Grunnmodus i drift | M2 ferdig | Q4, Q10, Q15, Q16, Q17, Q23 (besvart), Q25 |
| M4 Brytere | M3 ferdig | Q5 (Panopto), Q6 (Canon), Q19 |

## 5. Kilder til sannhet

- **Repoet er fasit fra nå.** Spesifikasjonen ble skrevet i Claude Docs og eksportert hit 21.10.2026; videre endringer gjøres i `docs/spec/*.md` og beslutningsloggen, ikke i Claude Docs. PDF-ene i `docs/spec/` er et øyeblikksbilde fra overleveringen og brukes for tegningene.
- **Ved konflikt:** beslutningslogg (nyeste rad) → ADR (akseptert) → `docs/design/`, `docs/studio/` → spesifikasjonen → konseptet → prototypen.
- **GUI:** `concept/` viser utseende og flyt. `docs/prototype/` er eldre og brukes bare som referanse for regel-ID-er.
