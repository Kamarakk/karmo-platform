"""Long-running local-only KARMO Worker service runner."""

from __future__ import annotations

import json
import signal
import time

from .health import health


def main() -> None:
    state = health()
    print(json.dumps(state, sort_keys=True), flush=True)
    if state["status"] != "healthy":
        raise SystemExit(1)

    running = True

    def stop(_signum: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        time.sleep(5)


if __name__ == "__main__":
    main()
