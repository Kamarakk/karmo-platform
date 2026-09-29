BEGIN;

-- Results too big for one 64 KiB worker-link frame (a spoken reply longer
-- than about a second) are uploaded by the worker in bounded pieces with
-- upload_result_piece, then assembled by submit_result. The result direction
-- of the large-arguments fix (fetch_arguments). Pieces are keyed by the
-- lease that wrote them, so a re-leased job never mixes pieces from an
-- earlier attempt. Nothing here is trusted: the assembled result still has
-- to match the worker's signed result envelope in accept_result() before
-- anything reaches karmo_worker_job_results. submit_result deletes a job's
-- pieces once the result is accepted.
CREATE TABLE IF NOT EXISTS public.karmo_worker_job_result_pieces (
    job_id UUID NOT NULL REFERENCES public.karmo_worker_jobs(job_id) ON DELETE CASCADE,
    lease_token UUID NOT NULL,
    offset_chars INTEGER NOT NULL CHECK (offset_chars >= 0),
    chunk TEXT NOT NULL CHECK (length(chunk) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (job_id, lease_token, offset_chars)
);

-- The SSH forced-command gateway connects as karmo_gateway (see migration
-- 009 for why every table it touches needs an explicit grant).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karmo_gateway') THEN
        GRANT INSERT, SELECT, DELETE ON public.karmo_worker_job_result_pieces TO karmo_gateway;
    END IF;
END
$$;

COMMIT;
