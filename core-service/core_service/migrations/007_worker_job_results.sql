BEGIN;

-- Model Router Phase D1 (see
-- docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md Section 6) --
-- closes a real architectural gap found while building the Core-side
-- dispatch/wait glue: the existing worker job/ticket/result system
-- (PR #41/#42) only ever durably stores a RESULT'S DIGEST and its
-- signature envelope (karmo_worker_jobs.result_digest/result_envelope)
-- -- it was built to let Core PROVE a claimed result is authentic, not
-- to let a separate later caller retrieve WHAT the answer actually was.
-- That is exactly right for a benchmark-style capability where the
-- expected output can be checked after the fact, but it cannot work for
-- a chat/tool-calling job, where Core has no way to know the model's
-- answer in advance -- it genuinely needs the real content back.
--
-- Mirrors karmo_worker_job_payloads' shape exactly (PR #41's own
-- pattern for job ARGUMENTS) for the symmetric RESULT side: one row per
-- job, cascade-deleted with it, the plaintext JSON plus its digest for
-- integrity cross-checking against the already-verified
-- result_envelope. Written only from
-- PostgresWorkerCoordinatorStore.submit_authenticated_result() at the
-- same point the envelope's signature has already been verified
-- (WorkerCoordinator.accept_result()) -- this table is never written
-- from unauthenticated input.
CREATE TABLE IF NOT EXISTS public.karmo_worker_job_results (
    job_id UUID PRIMARY KEY REFERENCES public.karmo_worker_jobs(job_id) ON DELETE CASCADE,
    result JSONB NOT NULL,
    result_digest TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMIT;
