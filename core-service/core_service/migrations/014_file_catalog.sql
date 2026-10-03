-- KARMO's data map: one row per file on Kamara's storage (the NAS and any
-- other configured source), so KARMO knows where things are without
-- copying them. Contents are opened only when a question needs them.
-- Written only by the catalog scan (role karmo_data_map_writer); the
-- chat path (karmo_core_memory) can only read it.
BEGIN;

CREATE TABLE IF NOT EXISTS public.karmo_file_catalog (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL CHECK (source ~ '^[a-z0-9_-]{1,40}$'),
    rel_path TEXT NOT NULL CHECK (length(rel_path) BETWEEN 1 AND 4096),
    name TEXT NOT NULL,
    ext TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    label TEXT NOT NULL,
    label_source TEXT NOT NULL DEFAULT 'rule' CHECK (label_source IN ('rule', 'owner', 'model')),
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    modified_at TIMESTAMPTZ NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    missing_since TIMESTAMPTZ,
    search tsvector GENERATED ALWAYS AS (
        to_tsvector('english', label || ' ' || kind || ' ' || regexp_replace(rel_path, '[/_.\-]+', ' ', 'g'))
    ) STORED,
    UNIQUE (source, rel_path)
);

CREATE INDEX IF NOT EXISTS karmo_file_catalog_search_idx ON public.karmo_file_catalog USING GIN (search);
CREATE INDEX IF NOT EXISTS karmo_file_catalog_label_idx ON public.karmo_file_catalog (label, kind, modified_at DESC);
CREATE INDEX IF NOT EXISTS karmo_file_catalog_seen_idx ON public.karmo_file_catalog (source, last_seen_at);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karmo_core_memory') THEN
        GRANT SELECT ON public.karmo_file_catalog TO karmo_core_memory;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karmo_data_map_writer') THEN
        GRANT SELECT, INSERT, UPDATE ON public.karmo_file_catalog TO karmo_data_map_writer;
        GRANT USAGE ON SEQUENCE public.karmo_file_catalog_id_seq TO karmo_data_map_writer;
    END IF;
END
$$;

COMMIT;
