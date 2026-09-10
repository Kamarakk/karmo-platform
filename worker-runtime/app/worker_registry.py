"""KARMO Worker Runtime -- Worker Registry (Phase 3).

WORKER, WORKER_CAPABILITY, WORKER_HEARTBEAT entities and the worker
lifecycle. Worker identity is explicit (caller-supplied, never inferred).
A worker's declared capabilities are validated against the closed
capability_manifest -- an availability CLAIM, never an authorization
grant (capability_manifest.py remains the sole authority on what each
capability_id means and is permitted to do).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum

from capability_manifest import CapabilityManifestError, validate_capability_declaration


class WorkerStatus(str, Enum):
    UNREGISTERED = "UNREGISTERED"
    REGISTERED = "REGISTERED"
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    DISABLED = "DISABLED"


class WorkerHealth(str, Enum):
    """What a worker may self-report on heartbeat -- deliberately NOT the
    same enum as WorkerStatus. A worker reports its own health; it never
    reports (and heartbeat() never accepts) coordinator-owned scheduling
    state like AVAILABLE/BUSY directly. Found and fixed after independent
    review: the prior heartbeat(..., status=...) accepted ANY WorkerStatus
    from the caller, letting a worker force itself AVAILABLE while the
    coordinator still held it BUSY on a live lease (or the reverse) --
    bypassing mark_busy()/mark_available()'s own lease-driven authority
    entirely."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"


class WorkerRegistryError(RuntimeError):
    pass


@dataclass
class WorkerRecord:
    worker_id: str
    hostname: str
    worker_version: str
    platform: str
    architecture: str
    registered_at: datetime
    last_seen: datetime
    status: WorkerStatus
    capabilities: list
    resource_limits: dict
    labels: list = field(default_factory=list)
    enabled: bool = True
    audit_trail: list = field(default_factory=list)

    def _record(self, event, now, note=""):
        self.audit_trail.append({"timestamp": now.isoformat(), "event": event, "note": note})


class WorkerRegistry:
    def __init__(self, *, clock=None, heartbeat_timeout_seconds=90):
        self._workers = {}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._heartbeat_timeout_seconds = heartbeat_timeout_seconds

    def _now(self):
        return self._clock()

    def register(
        self,
        *,
        worker_id,
        hostname,
        worker_version,
        platform,
        architecture,
        capabilities,
        resource_limits,
        labels=None,
    ):
        if not worker_id or not isinstance(worker_id, str):
            raise WorkerRegistryError("worker_id must be an explicit, non-empty string")

        # Validate every declared capability against the closed manifest
        # BEFORE accepting registration -- refuse the whole registration
        # on any invalid capability, not a partial acceptance.
        validated_capabilities = []
        for declaration in capabilities:
            validated = validate_capability_declaration(declaration)
            validated_capabilities.append(validated["capability_id"])

        now = self._now()
        existing = self._workers.get(worker_id)

        if existing is not None:
            # Duplicate registration: idempotent update if the identity
            # is CONSISTENT (same hostname/platform/architecture); a
            # conflicting identity under the same worker_id is refused
            # outright -- this is exactly the identity-spoofing shape
            # Phase 13's threat model names ("worker impersonation").
            if (existing.hostname, existing.platform, existing.architecture) != (hostname, platform, architecture):
                raise WorkerRegistryError(
                    f"worker_id {worker_id!r} already registered with a different identity "
                    f"(hostname/platform/architecture mismatch) -- refused, not overwritten; "
                    "this is the exact shape of a worker-impersonation attempt"
                )
            existing.worker_version = worker_version
            existing.capabilities = validated_capabilities
            existing.resource_limits = resource_limits
            existing.labels = labels or []
            existing.last_seen = now
            existing.status = WorkerStatus.REGISTERED if existing.status != WorkerStatus.DISABLED else WorkerStatus.DISABLED
            existing._record("re-registered", now)
            return existing

        record = WorkerRecord(
            worker_id=worker_id,
            hostname=hostname,
            worker_version=worker_version,
            platform=platform,
            architecture=architecture,
            registered_at=now,
            last_seen=now,
            status=WorkerStatus.REGISTERED,
            capabilities=validated_capabilities,
            resource_limits=resource_limits,
            labels=labels or [],
        )
        record._record("registered", now)
        self._workers[worker_id] = record
        return record

    def _require(self, worker_id):
        record = self._workers.get(worker_id)
        if record is None:
            raise WorkerRegistryError(f"no such worker: {worker_id!r}")
        return record

    def heartbeat(self, worker_id, *, health=None):
        """A worker heartbeat may report its own HEALTH (HEALTHY or
        DEGRADED) -- it can never set coordinator-owned scheduling state
        (AVAILABLE/BUSY/OFFLINE/DISABLED) directly. Scheduling state is
        exclusively mutated by the coordinator itself: mark_busy() /
        mark_available() around a lease, sweep_stale_workers() for
        absence, disable() for an admin action. This is the fix for the
        gap where a raw `status=` heartbeat parameter let a worker set
        itself AVAILABLE while actually BUSY on a live lease (or the
        reverse), bypassing lease-driven scheduling authority entirely."""
        record = self._require(worker_id)
        if record.status == WorkerStatus.DISABLED:
            raise WorkerRegistryError(f"worker {worker_id!r} is DISABLED -- heartbeat refused")

        if health is not None and health not in (WorkerHealth.HEALTHY, WorkerHealth.DEGRADED):
            raise WorkerRegistryError(f"invalid health value: {health!r} -- must be a WorkerHealth or None")

        now = self._now()
        record.last_seen = now

        if health == WorkerHealth.DEGRADED:
            # Self-reported health problem. Honored out of any
            # non-scheduling-owned state, but NEVER out of BUSY -- a
            # worker mid-lease cannot use a heartbeat to unilaterally
            # exit the coordinator's own BUSY tracking; only
            # finalize_success/finalize_failure (via mark_available) or
            # sweep_stale_workers (via absence) may ever move a worker
            # out of BUSY.
            if record.status in (WorkerStatus.AVAILABLE, WorkerStatus.REGISTERED, WorkerStatus.OFFLINE):
                record.status = WorkerStatus.DEGRADED
        elif record.status in (WorkerStatus.OFFLINE, WorkerStatus.REGISTERED, WorkerStatus.DEGRADED):
            # The only status transition a worker's own heartbeat may
            # ever trigger: "I'm reachable and healthy again" out of a
            # non-scheduling-owned state. Never out of BUSY.
            record.status = WorkerStatus.AVAILABLE

        record._record("heartbeat", now, note=f"status={record.status.value}, health={health.value if health else 'unspecified'}")
        return record

    def sweep_stale_workers(self):
        """Marks any worker whose last_seen exceeds the heartbeat timeout
        as OFFLINE -- called before any eligibility check, mirroring the
        Approval Engine's lazy-expiry pattern."""
        now = self._now()
        for record in self._workers.values():
            if record.status in (WorkerStatus.AVAILABLE, WorkerStatus.BUSY, WorkerStatus.DEGRADED):
                if now - record.last_seen > timedelta(seconds=self._heartbeat_timeout_seconds):
                    record.status = WorkerStatus.OFFLINE
                    record._record("marked-offline", now, note="heartbeat timeout exceeded")

    def disable(self, worker_id, *, reason=""):
        record = self._require(worker_id)
        now = self._now()
        record.status = WorkerStatus.DISABLED
        record._record("disabled", now, note=reason)
        return record

    def mark_busy(self, worker_id):
        record = self._require(worker_id)
        if record.status != WorkerStatus.AVAILABLE:
            raise WorkerRegistryError(f"cannot mark BUSY from {record.status.value} (must be AVAILABLE)")
        record.status = WorkerStatus.BUSY
        record._record("busy", self._now())
        return record

    def mark_available(self, worker_id):
        record = self._require(worker_id)
        if record.status not in (WorkerStatus.BUSY, WorkerStatus.DEGRADED):
            raise WorkerRegistryError(f"cannot mark AVAILABLE from {record.status.value}")
        record.status = WorkerStatus.AVAILABLE
        record._record("available", self._now())
        return record

    def is_eligible(self, worker_id, capability_id):
        self.sweep_stale_workers()
        record = self._workers.get(worker_id)
        if record is None:
            return False
        return (
            record.enabled
            and record.status == WorkerStatus.AVAILABLE
            and capability_id in record.capabilities
        )

    def eligible_workers(self, capability_id):
        self.sweep_stale_workers()
        return [
            record for record in self._workers.values()
            if record.enabled and record.status == WorkerStatus.AVAILABLE and capability_id in record.capabilities
        ]

    def get(self, worker_id):
        return self._require(worker_id)

    def all_workers(self):
        return list(self._workers.values())
