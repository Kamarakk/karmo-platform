"""KARMO Model Router Phase D2 -- Core's own worker-dispatch client.

dispatch_and_wait() (worker_dispatch.py, proven in Phase D1) needs a
`store`, an `approval_engine`, and a `gateway_backend` exposing
attach_job_arguments(). None of that requires any cryptographic
material: enqueueing a job, attaching its arguments, polling its state,
and reading back its result are pure database operations on the
worker-coordination tables -- the worker/ticket/result signing keys
only matter to the SSH forced-command gateway process that actually
receives a worker's connection (worker_gateway_runtime.py), never to
Core originating a dispatch.

This module is therefore deliberately its own narrow credential path,
separate from worker_gateway_runtime.build_backend()'s full config
(which also reads the SSH transport identity and HMAC key material Core
has no reason to hold). It needs exactly one thing: a Postgres DSN with
sufficient privilege on the worker-coordination tables -- reusing the
same role already granted that access for the gateway (karmo_gateway),
via its own dedicated DSN file Core's own service account can read,
never the gateway's SSH/HMAC credential directory.

**Deployment note, not yet provisioned as of this module's introduction**:
this DSN file does not exist in production yet. build_default_worker_dispatch_client()
degrades to NullWorkerDispatchClient (matching every other optional
subsystem's never-raise-on-construction discipline) until it is created
-- Phase D2's worker path simply never has a dispatch client available
and every chat turn falls back to the existing local candidate chain,
exactly as it does today. This is a deliberate, safe default: merging
this code changes no live behavior until that DSN is deployed as its
own separate, explicit step.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from .worker_coordination import PostgresWorkerCoordinatorStore
from .worker_gateway_backend import attach_job_arguments
from .worker_dispatch import dispatch_and_wait
from .control import ApprovalEngine
from .persistence import PostgresApprovalStore

DEFAULT_DISPATCH_DSN_FILE = "/etc/karmo/core/worker-dispatch.dsn"


class WorkerDispatchClientError(RuntimeError):
    pass


class NullWorkerDispatchClient:
    """Explicit degraded client, mirroring every other optional
    subsystem in operator.py (NullMemoryBackend, NullWorkerHealthReader,
    NullRouterDecisionRecorder). available=False tells the caller to
    skip the worker path entirely and go straight to local candidates --
    never attempted, never a raised exception mid-turn."""

    available = False

    def dispatch(self, **kwargs):
        raise WorkerDispatchClientError(
            "no worker dispatch DSN configured -- check available before calling dispatch()"
        )


class PostgresWorkerDispatchClient:
    available = True

    def __init__(self, *, connection_factory):
        self._connection_factory = connection_factory
        self.store = PostgresWorkerCoordinatorStore(connection_factory)
        self.approval_engine = ApprovalEngine(store=PostgresApprovalStore(connection_factory))
        # dispatch_and_wait() only ever calls attach_job_arguments() on the
        # gateway_backend it's given -- a minimal shim exposing exactly
        # that, backed by the same standalone function the real SSH
        # gateway's own backend delegates to, with none of that backend's
        # crypto-dependent construction requirements.
        self._gateway_backend = SimpleNamespace(
            attach_job_arguments=lambda **kw: attach_job_arguments(connection_factory, **kw)
        )

    def dispatch(self, *, worker_id, tool_id, tool_version, arguments,
                 total_deadline_seconds, lease_seconds=None, poll_interval_seconds=1.0, sleep=None):
        kwargs = dict(
            store=self.store,
            gateway_backend=self._gateway_backend,
            approval_engine=self.approval_engine,
            worker_id=worker_id,
            tool_id=tool_id,
            tool_version=tool_version,
            arguments=arguments,
            total_deadline_seconds=total_deadline_seconds,
            lease_seconds=lease_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )
        if sleep is not None:
            kwargs["sleep"] = sleep
        return dispatch_and_wait(**kwargs)


def build_default_worker_dispatch_client(dsn_file: str = DEFAULT_DISPATCH_DSN_FILE):
    path = Path(dsn_file)
    if not path.is_file():
        return NullWorkerDispatchClient()
    mode = path.stat().st_mode & 0o777
    if mode & 0o007:
        raise WorkerDispatchClientError("worker dispatch DSN file must not be accessible to other users")
    dsn = path.read_text(encoding="utf-8").strip()
    if not dsn:
        raise WorkerDispatchClientError("worker dispatch DSN file is empty")

    import psycopg

    def connection_factory():
        return psycopg.connect(dsn)

    return PostgresWorkerDispatchClient(connection_factory=connection_factory)
