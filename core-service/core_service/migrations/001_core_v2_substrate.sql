BEGIN;

CREATE TABLE IF NOT EXISTS public.tool_registry (
    tool_id TEXT NOT NULL,
    version TEXT NOT NULL,
    manifest JSONB NOT NULL,
    computed_approval_requirement TEXT NOT NULL,
    deprecated BOOLEAN NOT NULL DEFAULT FALSE,
    superseded_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tool_id, version)
);

CREATE TABLE IF NOT EXISTS public.tool_invocation_ledger (
    invocation_id UUID PRIMARY KEY,
    task_id UUID,
    tool_id TEXT NOT NULL,
    tool_version TEXT NOT NULL,
    requester TEXT NOT NULL,
    executor_identity TEXT,
    arguments_digest TEXT NOT NULL,
    approval_id UUID,
    status TEXT NOT NULL,
    result_digest TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS public.core_approval_records (
    approval_id UUID PRIMARY KEY,
    requester TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    tool_version TEXT NOT NULL,
    arguments_digest TEXT NOT NULL,
    authority_class TEXT NOT NULL,
    state TEXT NOT NULL,
    approver TEXT,
    authorized_executor TEXT,
    execution_binding TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.karmo_tasks (
    task_id UUID PRIMARY KEY,
    objective TEXT NOT NULL,
    requester TEXT NOT NULL,
    risk TEXT NOT NULL,
    allowed_capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    state TEXT NOT NULL,
    model TEXT,
    tool TEXT,
    inputs JSONB NOT NULL DEFAULT '{}'::jsonb,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    actions JSONB NOT NULL DEFAULT '[]'::jsonb,
    checkpoints JSONB NOT NULL DEFAULT '[]'::jsonb,
    failures JSONB NOT NULL DEFAULT '[]'::jsonb,
    retries INTEGER NOT NULL DEFAULT 0 CHECK (retries >= 0),
    approvals JSONB NOT NULL DEFAULT '[]'::jsonb,
    verification JSONB NOT NULL DEFAULT '[]'::jsonb,
    rollback JSONB,
    result JSONB,
    next_action TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.karmo_task_events (
    event_id UUID PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES public.karmo_tasks(task_id),
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_invocation_task ON public.tool_invocation_ledger(task_id);
CREATE INDEX IF NOT EXISTS idx_task_events_task_created ON public.karmo_task_events(task_id, created_at);
CREATE INDEX IF NOT EXISTS idx_karmo_tasks_state ON public.karmo_tasks(state);

COMMIT;
