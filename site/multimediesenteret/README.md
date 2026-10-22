# site/ntnu-studio

Alt som er spesielt for NTNU-studioet. Kan senere flyttes til et eget repo (`cutcut-site-ntnu-studio`, spesifikasjonen 12.2).

`devices.yaml` (utstyr, IP-er etter IP-planen, ikke bekreftet), `shows/` (1–4 personer, inngangskart D-054), `staff.yaml` (tom til Q33) og `equipment/`. Kommer: `setup/`, `baseline.yaml`. Ingen passord eller nøkler her.

Prøv oppsettet i simulatoren: `uv run cutcut sim --site site/ntnu-studio`.

| Mappe | Innhold |
| --- | --- |
| `equipment/obsbot/` | OSC-definisjon for Tail 2 og OBSBOT Center (fra OBSBOT). VISCA-tabellen ligger i Google Sheets (lenke i teknisk referanse) og skal lastes ned hit |
| `equipment/canon/` | XC-kommandoliste når den kommer (Q6) |
| `equipment/atem/` | Eksportert ATEM-oppsett og makroer (ATEM Television Studio HD8 ISO, D-053) |
| `equipment/multiview_map.yaml` | Rutekart for videolaget fra foto, inngangskart bekreftet (D-054) |
| `equipment/companion_map.yaml` | Companion side 10, peker på kamera-ID-er |
| `equipment/companion/` | `cutcut-pages.companionconfig` og eksisterende eksport |
