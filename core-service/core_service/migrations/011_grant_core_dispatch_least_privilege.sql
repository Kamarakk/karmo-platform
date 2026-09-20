BEGIN;

-- Model Router Phase D2 -- Core's own worker-dispatch credential (see
-- worker_dispatch_client.py's module docstring and
-- docs/project-state/CURRENT_STATE.md's 2026-09-19 D2 entry).
--
-- The original design reused karmo_gateway's role for Core's dispatch
-- DSN -- flagged by two independent reviews as over-privileged. Traced
-- exactly what dispatch_and_wait() (worker_dispatch.py) actually touches,
-- not guessed: it (1) writes and later updates exactly one approval
-- record, (2) enqueues one job row and polls its state back, (3) attaches
-- one job's arguments, and (4) reads one job's result -- never any of
-- karmo_gateway's much broader responsibilities (worker registration,
-- heartbeats, capability updates, execution tickets, revocation).
--
-- karmo_core_dispatch is a new, dedicated, least-privilege role scoped to
-- exactly the four tables that real trace touched, and nothing else --
-- no UPDATE on karmo_worker_jobs (that state transition happens on the
-- worker/gateway side, never Core's dispatch path), no access at all to
-- karmo_workers, karmo_execution_tickets, or karmo_worker_events.
--
-- karmo_core_dispatch is provisioned directly in production (CREATE ROLE,
-- no migration in this repo creates it), matching karmo_core_memory's
-- precedent (migration 006) -- this migration only grants it. Guarded
-- with the same pg_roles existence check as migrations 006/009 in case
-- this ever runs against an environment where the role doesn't exist.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karmo_core_dispatch') THEN
        GRANT INSERT, SELECT, UPDATE ON public.core_approval_records TO karmo_core_dispatch;
        GRANT INSERT, SELECT ON public.karmo_worker_jobs TO karmo_core_dispatch;
        GRANT INSERT, SELECT ON public.karmo_worker_job_payloads TO karmo_core_dispatch;
        GRANT SELECT ON public.karmo_worker_job_results TO karmo_core_dispatch;
    END IF;
END
$$;

COMMIT;
