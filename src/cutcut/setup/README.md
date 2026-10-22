# `cutcut.setup` – setup-hjelperen

Plan: [`docs/plans/setup-health.md`](../../../docs/plans/setup-health.md), spesifikasjonen 8.4 og 6.4. Teknikeren går gjennom ti steg i teknikervinduet (Oppsett). Stegene er data i `config/defaults/setup/NN-id.yaml` og kan overstyres i `site/<studio>/setup/`. Utskrevet veiledning: `uv run python tools/gen_setup_guide.py`.

| Fil | Innhold |
| --- | --- |
| `steps.py` | Stegene: «Sjekk steget», «Godkjenn steget» og «Fiks for meg» (HS-5, HS-6) |
| `multiview.py` | Rutekartet mot show-oppsettet og det ATEM viser, og anbefalt 2 + 8-oppsett. Funnene heter `H-MV-0` … `H-MV-11` (tabell i `docs/studio/multiview.md`) |
| `mic_check.py` | Steg 5: riktig kanal per mic, lekkasje mellom mikrofonene og støygulv. Lagres som fasit i `baseline.yaml`, og `audio-capture` får den nye lekkasjen med en gang |
| `color.py` | Steg 4, fargematching med gråkort (P8, F-10) |

**Stegene.** Hvert steg peker på helsesjekkene som viser resultatet (`H-CAM-C*` er lov).
- «Sjekk steget» kjører sjekkene med en gang (`HealthEngine.run_matching`). Det er de samme sjekkene som i drift, og de bare leser.
- «Godkjenn steget» lagres med tekniker og tid i databasen (`setup.approvals`) og logges. Et steg med rød sjekk kan ikke godkjennes, og en godkjenning skjuler aldri en sjekk som blir rød senere.
- «Fiks for meg» finnes bare der det er trygt (nå: ATEM-inngangsnavn i steg 3), krever bekreftelse og er sperret under opptak.
- API: `GET /api/setup/steps`, `POST /api/setup/steps/{steg}/check|fix|approve`.
- Et steg kan ha et panel i teknikervinduet (`panel:` i YAML-filen): `devices` (steg 1), `atem` (3), `color` (4), `mics` (5) og `multiview` (6).

**Fargematching (steg 4, `color.py`).** Med et gråkort foran hvert kamera finner CutCut kortet i hver kamerarute: jevne, fargeløse blokker som verken er mørke eller utbrent. Den måler rødt mot blått og lysstyrke, og justerer hvitbalanse (kelvin) og gain mot referansekameraet. Det skjer i høyst fem runder, til forskjellen er under 3 %. Kamerakommandoene går gjennom kameravakten, så et kamera på program eller preview hoppes over (I2). Siste resultat lagres i appen (`setup.color`) og brukes som start neste gang. API: `GET` og `POST /api/setup/color`.

Ingenting her flytter et kamera på lufta eller endrer ATEM under opptak.

Tester: `tests/unit/setup/`.
