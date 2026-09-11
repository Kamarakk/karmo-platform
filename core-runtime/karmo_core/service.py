"""Stable, local-only application boundary for KARMO Core v2.

The first production increment is deliberately inert with respect to external
systems: no listener, no database, no Qdrant, no subprocess execution, and no
secrets. It proves service lifecycle, configuration, health visibility, and a
fail-closed control boundary before any live integration is added.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class HealthState(str, Enum):
    STARTING = "STARTING"
    HEALTHY = "HEALTHY"
    FAILED = "FAILED"


@dataclass(frozen=True)
class CoreHealth:
    service: str
    state: HealthState
    failure_reason: str | None
    network_listener_enabled: bool
    persistent_writes_enabled: bool
    worker_transport_enabled: bool


class CoreService:
    """Minimal fail-closed Core service lifecycle.

    This is the production integration boundary, not a copy of the prototype
    directory. Capability/approval/job adapters can be added behind this
    boundary only after their semantics are validated against the approved
    Core v2 designs.
    """

    def __init__(self) -> None:
        self._state = HealthState.STARTING
        self._failure_reason: str | None = None

    def start(self) -> None:
        # No external dependencies are permitted in this rollout increment.
        self._state = HealthState.HEALTHY
        self._failure_reason = None

    def fail(self, reason: str) -> None:
        self._state = HealthState.FAILED
        self._failure_reason = reason or "UNSPECIFIED_FAILURE"

    def health(self) -> dict[str, Any]:
        return asdict(
            CoreHealth(
                service="karmo-core",
                state=self._state,
                failure_reason=self._failure_reason,
                network_listener_enabled=False,
                persistent_writes_enabled=False,
                worker_transport_enabled=False,
            )
        )
