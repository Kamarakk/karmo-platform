-- SYNTHETIC TEST-ONLY SCAFFOLDING. NOT part of the frozen H0.1 design.
--
-- The H0.1 migration (001_h01_karmo_outbox.sql) assumes public.conversation_memory
-- already exists from the frozen v0.5 schema. This repository does not contain
-- (and this agent is not authorized to inspect) the production v0.5 schema, so
-- this minimal synthetic table exists solely to give the isolated test database
-- a FK target with the columns transactional_memory.py actually reads/writes:
-- (role, content) -> RETURNING id, created_at. No production schema, data, or
-- structure beyond this was consulted or reproduced.

CREATE TABLE public.conversation_memory (
    id BIGSERIAL PRIMARY KEY,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
