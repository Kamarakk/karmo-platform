"""Proves the guardrails hold without any model. Run: python3 test_rules.py"""

from __future__ import annotations

import rules

BAD_PATHS = ["../orders.json", "/etc/passwd", "../../../.ssh/id_rsa", "", "sub/../../x"]
failures = 0
for bad in BAD_PATHS:
    try:
        rules.sandbox_path(bad)
        print(f"FAIL  allowed {bad!r}")
        failures += 1
    except ValueError as error:
        print(f"PASS  blocked {bad!r}: {error}")

ok = rules.sandbox_path("ticket.txt")
print(f"PASS  allowed 'ticket.txt' -> {ok.name}")

cases = {"A-1001": (True, False), "A-1002": (True, True), "A-1003": (False, None), "Z-9": (False, None)}
for order_id, (allowed, approval) in cases.items():
    result = rules.check_refund(order_id)
    good = result["allowed"] == allowed and (not allowed or result["needs_approval"] == approval)
    print(f"{'PASS' if good else 'FAIL'}  refund {order_id}: {result}")
    failures += 0 if good else 1

print("\nALL GUARDRAILS HOLD" if failures == 0 else f"\n{failures} FAILURE(S)")
raise SystemExit(1 if failures else 0)
