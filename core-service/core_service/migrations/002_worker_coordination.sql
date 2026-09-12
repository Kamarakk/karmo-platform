BEGIN;

CREATE TABLE IF NOT EXISTS public.karmo_workers (
    worker_id TEXT PRIMARY KEY,
    key_id TEXT NOT NULL,
    credential_version INTEGER NOT NULL DEFAULT 1 CHECK (credential_version > 0),
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','DRAINING','REVOKED')),
    capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ,
    lease_expires_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS public.karmo_worker_jobs (
    job_id UUID PRIMARY KEY,
    task_id UUID NOT NULL,
    approval_id UUID,
    tool_id TEXT NOT NULL,
    tool_version TEXT NOT NULL,
    arguments_digest TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('QUEUED','LEASED','RESULT_SUBMITTED','SUCCEEDED','FAILED','RECOVERY_REQUIRED','CANCELLED')),
    worker_id TEXT REFERENCES public.karmo_workers(worker_id),
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    result_digest TEXT,
    result_envelope JSONB,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT worker_job_lease_shape CHECK (
        (state='LEASED' AND worker_id IS NOT NULL AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)
        OR state<>'LEASED'
    )
);

CREATE TABLE IF NOT EXISTS public.karmo_execution_tickets (
    ticket_digest TEXT PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES public.karmo_worker_jobs(job_id),
    worker_id TEXT NOT NULL REFERENCES public.karmo_workers(worker_id),
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    CHECK (expires_at > issued_at)
);

CREATE TABLE IF NOT EXISTS public.karmo_worker_events (
    event_id UUID PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    worker_id TEXT,
    job_id UUID,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_worker_jobs_state_created ON public.karmo_worker_jobs(state, created_at);
CREATE INDEX IF NOT EXISTS idx_worker_jobs_lease_expiry ON public.karmo_worker_jobs(lease_expires_at) WHERE state='LEASED';
CREATE INDEX IF NOT EXISTS idx_worker_jobs_task ON public.karmo_worker_jobs(task_id);
CREATE INDEX IF NOT EXISTS idx_worker_ticket_job ON public.karmo_execution_tickets(job_id);
CREATE INDEX IF NOT EXISTS idx_worker_events_job ON public.karmo_worker_events(job_id, created_at);

COMMIT;
