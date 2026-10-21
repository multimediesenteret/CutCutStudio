# ui – skjermene

Skjermene for CutCut Studio: touch-skjermen i studio, teknikerskjermen og web-simulatoren.
Plan: [`docs/plans/ui.md`](../docs/plans/ui.md). Utseendet følger konseptet i `concept/`.

| Mappe             | Hva                                                                                                                                                                                       |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `packages/design` | Farger, ikoner, tegninger av bildeutsnitt, tema (lys/mørk).                                                                                                                               |
| `packages/client` | Tilstand (`Store`), transport (`WsTransport` mot motoren, `ReplayTransport` for forløp fra `uv run cutcut trace`), kommandoer og React-kroker. `api-types.ts` er generert – ikke rediger. |
| `apps/touch`      | Touch-skjermen (`/touch/`).                                                                                                                                                               |
| `apps/tech`       | Teknikerskjermen (`/tech/`).                                                                                                                                                              |

Skjermene viser bare tilstand fra motoren og sender kommandoer. De bestemmer aldri noe selv
(I1, I3). Mister de forbindelsen, viser de siste tilstand gråtonet og kobler til igjen.

## Kommandoer

```bash
pnpm install          # første gang (Node 22+, corepack enable)
pnpm types            # generer klienttyper etter endring i API-et (docs/reference/openapi.json)
pnpm lint && pnpm typecheck && pnpm test
pnpm build            # bygger til ui/dist/{touch,tech}, som motoren serverer
pnpm --filter @cutcut/touch dev   # utvikling mot motor/simulator på 127.0.0.1:8080
```
