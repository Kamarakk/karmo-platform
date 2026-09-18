BEGIN;

-- Model Router Phase C -- worker-side shadow-routing read (see
-- docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md Section 3.8).
--
-- shadow_router.py's build_default_worker_health_reader() reuses
-- core-service's existing memory DSN (karmo_core_memory role) to read
-- public.karmo_workers.ollama_snapshot/ollama_snapshot_at, on the
-- assumption that a DSN pointed at the same database implied broad
-- access to it. That assumption was wrong, found live during Phase C's
-- production deployment: karmo_core_memory is a deliberately
-- least-privileged role scoped to memory tables only, and correctly
-- refused the read ("permission denied for table karmo_workers").
--
-- Fix is the minimal grant actually needed, not a design change or a
-- new credential: SELECT only, on this one table, for this one role.
-- karmo_core_memory still cannot write to karmo_workers, still cannot
-- read/write any worker-coordination table beyond this single read
-- path (karmo_worker_jobs, karmo_execution_tickets, karmo_worker_events
-- remain ungranted) -- shadow routing only ever reads
-- ollama_snapshot/ollama_snapshot_at/last_seen_at via
-- get_worker_ollama_health(), never anything else on this table.
--
-- karmo_core_memory is a production-provisioned role, not one any
-- migration in this repo creates (like the worker/gateway accounts in
-- docs/runbooks/WORKER01_EXACT_ACTIVATION.md, it was provisioned
-- directly). No test fixture in this repo applies this file, and it is
-- never run against CI's test Postgres -- but guarded anyway, matching
-- the ADD COLUMN IF NOT EXISTS idempotency already used in 005, in case
-- this ever runs against an environment where the role doesn't exist.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karmo_core_memory') THEN
        GRANT SELECT ON public.karmo_workers TO karmo_core_memory;
    END IF;
END
$$;

COMMIT;
