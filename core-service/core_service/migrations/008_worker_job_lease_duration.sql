BEGIN;

-- Model Router Phase D1 reliability fix (see
-- docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md Section 6) --
-- closes a real bug found via a live production proof-run tonight:
-- worker_gateway_backend.py's poll() always leased jobs via the
-- store's fixed 60-second default, regardless of which capability was
-- actually being executed, while model_chat/model_chat_tools both
-- declare a 120-second timeout_seconds in their manifest. A real call
-- approaching or exceeding 60s could structurally never report its own
-- success before its lease expired -- confirmed live: the underlying
-- Ollama tool-calling call very likely succeeded, but the worker's
-- submit_result was refused because the lease had already expired.
--
-- requested_lease_seconds is set at enqueue time by whoever is
-- creating the job -- the party that actually knows which capability
-- is being invoked and roughly how long it needs -- and consulted
-- automatically by lease_job(). No cross-package capability-manifest
-- lookup needed on the Core side; no wire-protocol change to poll()
-- itself (it still calls lease_job() with no explicit lease_seconds,
-- and now correctly picks up whatever the job's own enqueuer
-- requested). NULL means "no opinion, use the existing 60s default" --
-- fully backward compatible with every job enqueued before this column
-- existed and every caller that never sets it.
ALTER TABLE public.karmo_worker_jobs
    ADD COLUMN IF NOT EXISTS requested_lease_seconds INTEGER NULL;

ALTER TABLE public.karmo_worker_jobs
    DROP CONSTRAINT IF EXISTS karmo_worker_jobs_requested_lease_seconds_check;

ALTER TABLE public.karmo_worker_jobs
    ADD CONSTRAINT karmo_worker_jobs_requested_lease_seconds_check
        CHECK (requested_lease_seconds IS NULL OR requested_lease_seconds BETWEEN 30 AND 600);

COMMIT;
