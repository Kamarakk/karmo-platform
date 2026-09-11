"""Long-running local service runner for KARMO Core."""

from __future__ import annotations

import json
import signal
import time

from .service import CoreService


def main() -> None:
    service = CoreService()
    service.start()
    print(json.dumps(service.health(), default=str), flush=True)

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
