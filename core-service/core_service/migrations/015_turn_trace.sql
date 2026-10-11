-- One row per chat turn: what KARMO was asked, what it answered, how it
-- got there (route, tools, model, host), what it cost (tokens, time) and
-- Kamara's thumbs up/down. Written by the chat path after every turn so a
-- bad answer can be traced to its cause instead of guessed at.
BEGIN;

CREATE TABLE IF NOT EXISTS public.karmo_turn_trace (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    question TEXT NOT NULL CHECK (length(question) <= 4000),
    answer TEXT NOT NULL CHECK (length(answer) <= 8000),
    route TEXT CHECK (length(route) <= 40),
    tools TEXT[] NOT NULL DEFAULT '{}',
    model TEXT CHECK (length(model) <= 120),
    host TEXT CHECK (length(host) <= 20),
    model_calls INTEGER NOT NULL DEFAULT 0 CHECK (model_calls >= 0),
    prompt_tokens INTEGER CHECK (prompt_tokens >= 0),
    output_tokens INTEGER CHECK (output_tokens >= 0),
    model_ms INTEGER CHECK (model_ms >= 0),
    latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
    error TEXT CHECK (length(error) <= 200),
    rating SMALLINT CHECK (rating IN (-1, 1)),
    rated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS karmo_turn_trace_created_idx ON public.karmo_turn_trace (created_at DESC);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'karmo_core_memory') THEN
        GRANT SELECT, INSERT ON public.karmo_turn_trace TO karmo_core_memory;
        GRANT UPDATE (rating, rated_at) ON public.karmo_turn_trace TO karmo_core_memory;
        GRANT USAGE ON SEQUENCE public.karmo_turn_trace_id_seq TO karmo_core_memory;
    END IF;
END
$$;

COMMIT;
