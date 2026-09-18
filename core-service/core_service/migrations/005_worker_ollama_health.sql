BEGIN;

-- Model Router Phase A -- worker-side health signal (see
-- docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md Section 3.1).
-- Both nullable: a worker that hasn't reported yet (an older worker
-- binary, or a heartbeat whose local Ollama probe failed) simply has
-- NULL here, never a misleading empty-but-present value.
--
-- ollama_snapshot_at is deliberately a separate column from last_seen_at
-- (which already updates on every heartbeat regardless of whether a
-- snapshot was included) -- WorkerCoordination.heartbeat() only writes
-- these two columns together, on a heartbeat that actually carried a
-- snapshot, and leaves the prior value in place otherwise. That lets a
-- future consumer tell exactly how stale the SNAPSHOT itself is,
-- independent of whether the worker is alive at all -- required for the
-- plan's Section 3.9 "health data stale -> exclude the host" rule to be
-- checkable at all.
ALTER TABLE public.karmo_workers
    ADD COLUMN IF NOT EXISTS ollama_snapshot JSONB NULL,
    ADD COLUMN IF NOT EXISTS ollama_snapshot_at TIMESTAMPTZ NULL;

COMMIT;
