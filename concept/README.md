# GUI-konsept (Vercel)

Statisk konsept av de to skjermene i CutCut Studio, på simulerte data. Ingen byggesteg: filene publiseres som de er.

| Fil | Hva |
| --- | --- |
| `index.html` | Begge skjermene side om side som skalerte 16:9-skjermer, med samme simulering |
| `touch.html` | Touch-skjermen i studio (1920 × 1080, kiosk). Mørkt tema som standard |
| `tech.html` | Teknikervinduet (vanlig nettleservindu på 16:9-skjerm). Følger systemtema |
| `assets/tokens.css` | Farger, typografi og felles regler (tokens fra `docs/design/farger.md`) |
| `assets/sim.js` | Forenklet regelmotor og simulert tale. Deler tilstand mellom faner med `BroadcastChannel` |
| `assets/views.js` | Simulerte kamerabilder, bordplan, ikoner, logo og tema |

## Kjøre lokalt

```bash
cd concept && python3 -m http.server 8765
# åpne http://localhost:8765
```

## Vercel

Konseptet er et arkiv. Forsiden på https://cutcutstudio2026.vercel.app er web-simulatoren (`/sim/`), og konseptet ligger på `/concept/` (D-053). Se `vercel.json` og `docs/publishing.md`.

## Antagelser

Kamerakart, IP-adresser og noen standardverdier er antatt for å kunne vise skjermene. Se «Antagelser i konseptet» i `docs/design/gui-konsept.md` og Q26.

## Hva som er konsept og hva som blir appen

- De ekte skjermene er bygget i `ui/apps/touch` og `ui/apps/tech` etter dette konseptet. Ved uenighet gjelder `ui/`.
- `sim.js` er en forenklet regelmotor for demo. Den ekte motoren er Python og sender tilstand over WebSocket; `BroadcastChannel` brukes bare her.
- Alt bruker teknologi som virker i Edge/WebView2 på Windows uten nett: systemskrift (Segoe UI Variable, Cascadia Mono), ren CSS og SVG, ingen CDN, ingen service worker. Se `docs/design/gui-konsept.md`.
