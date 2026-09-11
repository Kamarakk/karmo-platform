"""Local-only health boundary for the production Worker service."""

from __future__ import annotations

from . import __version__


def health() -> dict:
    try:
        from core_service.control import CapabilityClass, compute_approval_requirement
    except Exception as exc:  # fail closed if Core is unavailable/broken
        return {
            "service": "karmo-worker",
            "version": __version__,
            "status": "unhealthy",
            "failure_reason": f"CORE_BINDING_UNAVAILABLE:{type(exc).__name__}",
            "core_bound": False,
            "network_listener": False,
            "worker_network_transport": False,
            "capability_execution_enabled": False,
            "persistent_writes": False,
        }

    requirement = compute_approval_requirement(CapabilityClass.READ)
    return {
        "service": "karmo-worker",
        "version": __version__,
        "status": "healthy",
        "failure_reason": None,
        "core_bound": True,
        "core_read_approval_floor": requirement.value,
        "network_listener": False,
        "worker_network_transport": False,
        "capability_execution_enabled": False,
        "persistent_writes": False,
    }
