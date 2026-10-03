-- Facts Kamara explicitly tells KARMO to remember ("remember that ..."),
-- given to the chat model on every turn. Written and deleted only by
-- Kamara's own "remember"/"forget fact N" commands, never by the model.
BEGIN;

CREATE TABLE IF NOT EXISTS public.karmo_owner_facts (
    id BIGSERIAL PRIMARY KEY,
    fact TEXT NOT NULL CHECK (length(fact) BETWEEN 1 AND 500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karmo_core_memory') THEN
        GRANT SELECT, INSERT, DELETE ON public.karmo_owner_facts TO karmo_core_memory;
        GRANT USAGE ON SEQUENCE public.karmo_owner_facts_id_seq TO karmo_core_memory;
    END IF;
END
$$;

COMMIT;
