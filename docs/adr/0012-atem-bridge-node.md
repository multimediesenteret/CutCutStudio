# ADR-0012: En egen liten prosess, atem-bridge, i Node.js med atem-connection, som snakker med regi-core over den interne meldingsbussen

- **Status:** Forslag
- **Dato:** 2026-10-20
- **Kilde:** spesifikasjonen 13.4

## Kontekst

atem-connection er det mest brukte og best vedlikeholdte ATEM-biblioteket (brukes av Companion og NRK Sofie); Python-alternativet er mindre brukt.

## Beslutning

En egen liten prosess, atem-bridge, i Node.js med atem-connection, som snakker med regi-core over den interne meldingsbussen.

## Konsekvenser

Én Node-runtime i tillegg til Python. Agenten bekrefter eller avviser i implementasjonsplanen for ATEM, etter Q7.
