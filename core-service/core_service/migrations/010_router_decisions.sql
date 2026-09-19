BEGIN;

-- Model Router Phase E -- decision auditing (see
-- docs/architecture/KARMO_MODEL_ROUTER_DESIGN_PLAN.md Section 3.6). A
-- routing trace, never a transcript: which host/model was chosen, what
-- signal values were read, and why -- content-restricted by both this
-- schema (no free-text prompt/result column exists to put anything in)
-- and by router_decision_audit.py's own enforced field allowlist on the
-- `candidates` payload before it ever reaches this INSERT.
CREATE TABLE IF NOT EXISTS public.karmo_router_decisions (
    decision_id UUID PRIMARY KEY,
    correlation_id TEXT NOT NULL,
    decision_kind TEXT NOT NULL CHECK (decision_kind IN ('shadow', 'live')),
    chosen_host TEXT,
    chosen_model TEXT,
    reason TEXT NOT NULL,
    candidates JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Populated later, once a live (Phase D2) decision's dispatch
    -- actually resolves -- NULL for shadow decisions, which never
    -- dispatch anything.
    outcome TEXT CHECK (outcome IS NULL OR outcome IN ('success', 'failure', 'timeout')),
    outcome_latency_ms INTEGER CHECK (outcome_latency_ms IS NULL OR outcome_latency_ms >= 0),
    outcome_recorded_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_router_decisions_correlation_id
    ON public.karmo_router_decisions(correlation_id);
CREATE INDEX IF NOT EXISTS idx_router_decisions_created_at
    ON public.karmo_router_decisions(created_at);

-- karmo_core_memory is the role core-service's operator.py already holds
-- a connection for (durable chat memory) -- reused here rather than a
-- new credential path, per the same System-Fit Review reasoning as
-- shadow_router.py's worker-health read. karmo_core_memory is a
-- production-provisioned role, not one any migration in this repo
-- creates; guarded the same way as migrations 006/009.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karmo_core_memory') THEN
        GRANT INSERT, SELECT, UPDATE ON public.karmo_router_decisions TO karmo_core_memory;
    END IF;
END
$$;

COMMIT;
