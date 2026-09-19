BEGIN;

-- Model Router Phase D1 production incident (2026-09-19, see
-- docs/project-state/CURRENT_STATE.md and
-- PROJECT_SAVE_2026-09-19_MODEL_ROUTER_REVIEW_FOR_CHATGPT.md).
--
-- Root cause, confirmed live: the SSH forced-command gateway process
-- connects to Postgres as `karmo_gateway`, not the schema-owning `karmo`
-- role that applies migrations. Migration 007 created
-- public.karmo_worker_job_results with no explicit GRANT, unlike the
-- pre-existing public.karmo_worker_job_payloads table, which
-- `karmo_gateway` already has INSERT on (granted directly in
-- production, outside any migration in this repo -- confirmed live via
-- has_table_privilege as a control comparison). Every submit_result
-- call for a capability that provides real result content therefore
-- hit an InsufficientPrivilege error on the INSERT inside
-- submit_authenticated_result()'s transaction, which rolled back the
-- just-applied state='RESULT_SUBMITTED' UPDATE in the same transaction
-- too -- explaining why affected jobs were left stuck at LEASED with no
-- RESULT_SUBMITTED event at all, while heartbeat/poll/authorize_execution
-- (which never touch this table) kept working the entire time. This was
-- invisible to every existing test because they all connect as the
-- schema-owning role, which always has implicit full access to tables
-- it owns.
--
-- Fix is the minimal grant actually needed: INSERT (to write a result)
-- and SELECT (get_worker_job_result() reads it back, via the same
-- karmo_gateway-authenticated connection used by the D1 dispatch
-- harness) on this one table, for this one role. No other privilege,
-- no other table, no change to karmo_gateway's existing access
-- elsewhere.
--
-- karmo_gateway is a production-provisioned role, not one any migration
-- in this repo creates (like karmo_core_memory in migration 006) -- no
-- test fixture in this repo applies this file automatically; guarded
-- with the same pg_roles existence check as migration 006 in case this
-- ever runs against an environment where the role doesn't exist.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karmo_gateway') THEN
        GRANT INSERT, SELECT ON public.karmo_worker_job_results TO karmo_gateway;
    END IF;
END
$$;

COMMIT;
