# `cutcut.audio` – `audio-capture`

Egen prosess (ADR-0014, PL-02) som leser multitrack fra RØDECaster og sender bare målinger til `core`. Rå lyd går aldri på bussen eller til disk.

| Fil | Innhold |
| --- | --- |
| `channels.py` | Kanalkart: mic N på multitrack-kanal `2 × N + 1` (D-032), hovedmiks på 1–2 |
| `dsp.py` | Nivå (RMS i dB) og 48 → 16 kHz nedsampling som strømmer mellom blokker |
| `vad.py` | Silero VAD (studio, ekstra `silero` + `models/silero_vad.onnx`) og energi-VAD (tester, reserve) |
| `analyzer.py` | 10 ms-blokker → `audio.frame`: `vad`, `level_db`, `dominance_db`, `pause_ms` per mic. Frasegrenser (AU-3) og lekkasje (AU-4) kommer |
| `backend.py` | Hvor lyden kommer fra: `fake` spiller en 48 kHz WAV; ASIO/WASAPI kommer i AU-5 |
| `process.py`, `main.py` | Løkka og `cutcut audio --wav fil.wav` |

```bash
uv sync --extra silero && uv run python tools/fetch_models.py   # Silero-modellen, sjekket med SHA-256
uv run cutcut audio --wav opptak.wav                             # spill av til en kjørende core
```

Tester (`tests/unit/audio/`) bruker syntetiske signaler, aldri ekte opptak av personer. En test viser at målingene får den ekte motoren til å klippe til den som snakker.
