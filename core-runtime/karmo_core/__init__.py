"""Productionized KARMO Core control boundary.

This package intentionally exposes no network listener and performs no
production database or Qdrant writes. It provides a stable local application
boundary around the already-verified Core v2 control concepts.
"""

from .service import CoreService, HealthState

__all__ = ["CoreService", "HealthState"]
