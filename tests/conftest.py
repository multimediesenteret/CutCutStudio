"""Test-wide setup."""

from cutcut.common.bus.zmq_bus import use_selector_event_loop

# The bus tests (and core through TestClient) need the selector loop on Windows, like the
# real processes (cutcut.common.bus.zmq_bus.use_selector_event_loop).
use_selector_event_loop()
