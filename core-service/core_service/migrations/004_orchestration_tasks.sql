BEGIN;

-- KARMO orchestration task board: durable, approval-gated tasks a
-- human-operated Claude Code or ChatGPT session reads and completes
-- manually. Intentionally not automated model dispatch -- no API key,
-- no outbound model call lives anywhere in this table's consumers.
-- KARMO stays the durable source of truth; every write goes through the
-- existing CapabilityRegistry + ApprovalEngine + CapabilityDispatcher,
-- never a separate authority path.
CREATE TABLE IF NOT EXISTS public.karmo_orchestration_tasks (
    task_id UUID PRIMARY KEY,
    objective TEXT NOT NULL,
    context TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLAIMED','DONE','CANCELLED')),
    requested_by TEXT NOT NULL,
    claimed_by TEXT,
    result TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_orchestration_tasks_status
    ON public.karmo_orchestration_tasks(status);

COMMIT;
