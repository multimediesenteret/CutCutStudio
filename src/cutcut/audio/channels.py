"""Which multitrack channel is which microphone (docs/studio/rodecaster-standardoppsett.md).

Mic N is on fader N and on USB 1 multitrack channel ``2 × N + 1`` (1-based, left of the
stereo pair). Channels 1–2 are the main mix. Fader 5 is the laptop (``M5``).
"""

from __future__ import annotations

from typing import Final

from cutcut.common.ids import MicId

SAMPLE_RATE: Final = 48_000
CHANNELS: Final = 20  # RØDECaster Pro II multitrack over USB 1
MAIN_MIX: Final = (0, 1)  # 0-based


def mic_channel(mic: MicId) -> int:
    """0-based channel index of a mic: M1 → 2, M2 → 4 … M5 → 10."""
    n = int(mic.value[1:])
    return 2 * n


DEFAULT_MAP: Final[dict[MicId, int]] = {mic: mic_channel(mic) for mic in MicId}
