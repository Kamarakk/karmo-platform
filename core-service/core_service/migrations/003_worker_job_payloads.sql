BEGIN;

-- Remote workers need the exact authorized arguments, not merely their digest.
-- Keep those arguments in a separate immutable row so the PR #41 job/ticket
-- state machine remains unchanged. A job without this row is not remotely
-- dispatchable and therefore fails closed.
CREATE TABLE IF NOT EXISTS public.karmo_worker_job_payloads (
    job_id UUID PRIMARY KEY REFERENCES public.karmo_worker_jobs(job_id) ON DELETE CASCADE,
    arguments JSONB NOT NULL,
    arguments_digest TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_worker_job_payload_digest
    ON public.karmo_worker_job_payloads(arguments_digest);

COMMIT;
