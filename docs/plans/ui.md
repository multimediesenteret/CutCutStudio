# Plan: `ui` – touch, tekniker og web-simulator

Status: forslag (M0) · Milepæl: M1 · Spes. 8, 12.5; D-036–D-039, D-043, D-045; ADR-0007, ADR-0013 · Mappe: `ui/`

## 1. Formål og avgrensning

De ekte skjermene i React + TypeScript, bygget etter `concept/` og `docs/design/`. Samme apper kjører i studio (mot motoren) og på Vercel (mot simulerte data).

| App/pakke | Innhold |
| --- | --- |
| `ui/packages/design` | Tokens fra `docs/design/farger.md` (status- og deltakerfarger, lyst/mørkt), typografi (Segoe UI Variable, Cascadia Mono), komponenter: knapp, hold-knapp med ring, mic-stripe, setebrikke, statusrad, varsel, multiview-rute, tidslinje (canvas) |
| `ui/packages/client` | Typer generert fra OpenAPI, `Transport`-grensesnitt, tilstandslager, tekster (`nb.json`) |
| `ui/apps/touch` | Fem skjermer: hvile → klar → lydsjekk 3–2–1 → opptak → ferdig (D-036). Fast 1920 × 1080, skalert |
| `ui/apps/tech` | Oversikt på én side (D-037), meny: Regi, Kameraer, Opptak, Helse, Oppsett, Logg, Innstillinger; roller (D-045) |
| `ui/apps/simulator` | Vercel: begge skjermene + kontrollpanel og banner «SIMULATOR – ingen ekte utstyr» (ADR-0013) |

## 2. Grensesnitt

```ts
interface Transport {
  connect(onMessage: (m: ServerMessage) => void): void;
  send(cmd: ClientCommand): Promise<CommandResult>;   // samme kommandoer som REST
  status(): "connected" | "reconnecting";
}
// WsTransport: ekte motor.  ReplayTransport: spiller av Trace-JSON (trinn 1).
// PyodideTransport: motoren i nettleseren (trinn 2, etter M1).
```

Appene vet ikke hvilken transport de bruker. Det er hele forskjellen mellom studio og Vercel.

**Krav som videreføres fra konseptet (`docs/design/gui-konsept.md`):** 10 Hz tilstand, bare endringer skrives til DOM, målere med `transform: scaleX()`, tidslinje på canvas, CPU i hovedtråden under 30 ms/s (touch) og 50 ms/s (tekniker). Ingen CDN, ingen nettfonter, ingen service worker, ingen `alert`/`confirm`, bare pointer events. Alt fungerer offline i Edge/WebView2.

**Robusthet for døgnet rundt:**

- Mister skjermen forbindelsen, vises siste tilstand grået ut med «Kobler til igjen» (12.5); den blir aldri blank.
- Touch sender hjerteslag; motoren varsler og kiosk-vakten laster siden på nytt hvis den stopper (`supervisor-ops.md`).
- Touch laster seg selv på nytt hver natt når ingen økt er aktiv (hindrer at minne vokser over uker).
- Ingen tilstand i nettleseren utenom tema; alt annet kommer fra motoren.

## 3. Tilstander og feil

Touch-stegene styres av motoren (`touch`-emnet), ikke av appen; teknikeren kan flytte dem (`POST /touch/step`). Feil på touch: bare én setning uten teknikk, og «Trenger du hjelp?». Gule avvik vises aldri for brukeren.

## 4. Avhengigheter

Node 24 LTS, pnpm 10 (Corepack), React 19, TypeScript strict, Vite, Vitest, Playwright, ESLint, Prettier, `openapi-typescript`. Ingen UI-bibliotek utenom React (konseptet viser at det ikke trengs, og det holder pakken liten).

## 5. Testplan

- Playwright: skjermbildetest per touch-steg i mørkt og lyst tema, og for teknikerens oversikt (12.5).
- Playwright: hele touch-flyten mot simulatoren (ferdig-kriteriet for spes. 11 steg 3).
- Ytelsestest i CI: CPU i hovedtråden måles med Chrome DevTools Protocol over 30 s; feiler over grensene.
- Vitest for tilstandslager og transport (gjenoppkobling, tapt sekvens).
- Minnetest: touch i 12 timer simulert tid i nattlig jobb, heap skal ikke vokse.

## 6. Leveranser

| # | Leveranse | Ferdig når |
| --- | --- | --- |
| U-1 | pnpm-arbeidsområde, CI-jobb `ui`, design-tokens fra konseptet | `pnpm build` og lint grønt |
| U-2 | Komponenter (knapp, hold-knapp, mic-stripe, setebrikke, statusrad) | Vitest + skjermbilder |
| U-3 | Klient: generert typer, `WsTransport`, `ReplayTransport`, lager | Gjenoppkobling testet |
| U-4 | Touch: hvile og klar | Ser ut som konseptet |
| U-5 | Touch: lydsjekk, opptak, ferdig, hold-for-avslutt, utlogging | Playwright-flyt grønn mot simulator |
| U-6 | Tekniker: oversikt (multiview, tidslinje, mic, logg, PGM/PVW) | Under 50 ms/s CPU |
| U-7 | Tekniker: Opptak, Helse, Logg, Kameraer (lesing) | Roller skjuler riktige menyer |
| U-8 | Tekniker: Regi (tuning og brytere), Innstillinger | Endringer virker straks (ADR-0011) |
| U-9 | Simulator-app med kontrollpanel og banner, bygget på Vercel | Forhåndsvisning per PR viser samme skjermer som studio |
| U-10 | Bytte Vercel fra `concept/` til simulatoren (`vercel.json`, eier godkjenner) | `cutcutstudio2026.vercel.app` viser simulatoren; `concept/` beholdes som arkiv |

Oppsett-veiviseren i teknikervinduet bygges i M3 (`setup-health.md`).

## 7. Åpne spørsmål

- Q32: skal standardvalget på klar-skjermen være 2 personer og video (D-036), eller hentes fra studio-oppsettet?
- Q15: kabellengde til touch-skjermen påvirker ikke koden, men kiosk-oppsettet.
- Vercel: godkjenning av `ignoreCommand` og byggekommando (se `milestones.md`, Q27).
</content>
</invoke>
