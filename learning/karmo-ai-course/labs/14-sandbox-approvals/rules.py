"""The guardrails. Pure code, no model. This is the part KARMO Core owns."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SANDBOX = (HERE / "sandbox").resolve()
ORDERS = HERE / "orders.json"
APPROVAL_OVER = 50.00


def sandbox_path(path: str) -> Path:
    """Resolve a path and refuse anything that escapes the sandbox folder."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError("A relative path is required.")
    if Path(path).is_absolute():
        raise ValueError("Absolute paths are not allowed.")
    target = (SANDBOX / path).resolve()
    if not target.is_relative_to(SANDBOX):
        raise ValueError("Path escapes the sandbox.")
    return target


def check_refund(order_id: str) -> dict:
    """Decide whether a refund may happen, and whether a human must approve it."""
    orders = json.loads(ORDERS.read_text(encoding="utf-8"))
    order = orders.get(order_id)
    if order is None:
        return {"allowed": False, "reason": f"Order {order_id} does not exist."}
    if order["refunded"]:
        return {"allowed": False, "reason": f"Order {order_id} was already refunded."}
    return {"allowed": True, "amount": order["paid"], "needs_approval": order["paid"] > APPROVAL_OVER}


def mark_refunded(order_id: str) -> None:
    orders = json.loads(ORDERS.read_text(encoding="utf-8"))
    orders[order_id]["refunded"] = True
    ORDERS.write_text(json.dumps(orders, indent=2) + "\n", encoding="utf-8")
