"""CLI for the production-safe KARMO Worker boundary."""

import json
import sys

from .health import health


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "health"
    if command != "health":
        print(json.dumps({"status": "error", "reason": f"unsupported command: {command}"}))
        return 2
    state = health()
    print(json.dumps(state, sort_keys=True))
    return 0 if state["status"] == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())
