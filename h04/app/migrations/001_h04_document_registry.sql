-- KARMO H0.4 document registry schema.
--
-- Authoritative PostgreSQL registry of logical document identity, archive
-- location, expected chunk count, versioning, and pipeline/embedding/
-- chunker provenance. Used only to reconcile PostgreSQL (expected state)
-- against actual Qdrant vector state and archived-file state; the auditor
-- built on top of this table is report-only (see app/auditor.py).
--
-- Authored and isolated-acceptance-tested as an isolated build artifact.
-- Applied to the production database as part of the H0.4 production
-- cutover (see docs/project-state/CURRENT_STATE.md, H0.4 section, and
-- docs/project-state/COMMAND_LOG.md for the cutover backup taken first).

CREATE TABLE public.document_registry (
    id BIGSERIAL PRIMARY KEY,

    -- Stable logical identity across versions (H0.2 document_id semantics).
    document_id TEXT NOT NULL,
    document_version INTEGER NOT NULL,

    -- Per-version SHA-256 content identity (H0.1/H0.2 document_hash
    -- semantics), preserved verbatim as the join key against Qdrant's
    -- document_hash payload field.
    document_hash TEXT NOT NULL,

    archive_source_location TEXT NOT NULL,
    expected_chunk_count INTEGER NOT NULL,

    pipeline_version TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    chunker_version TEXT NOT NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    superseded_by TEXT,
    source_path TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deactivated_at TIMESTAMPTZ,

    CONSTRAINT document_registry_hash_unique UNIQUE (document_hash),

    CONSTRAINT document_registry_hash_format_check
        CHECK (document_hash ~ '^[0-9a-f]{64}$'),

    CONSTRAINT document_registry_version_check
        CHECK (document_version >= 1),

    CONSTRAINT document_registry_chunk_count_check
        CHECK (expected_chunk_count >= 1),

    CONSTRAINT document_registry_identity_nonempty_check
        CHECK (
            length(document_id) BETWEEN 1 AND 512
            AND length(archive_source_location) BETWEEN 1 AND 4096
            AND length(pipeline_version) BETWEEN 1 AND 128
            AND length(embedding_model) BETWEEN 1 AND 128
            AND length(chunker_version) BETWEEN 1 AND 128
        ),

    CONSTRAINT document_registry_deactivated_state_check
        CHECK (
            (is_active AND deactivated_at IS NULL)
            OR (NOT is_active AND deactivated_at IS NOT NULL)
        )

    -- Deliberately NOT enforced here: "only one active version per
    -- document_id". That invariant is normally kept by the H0.2 ingest
    -- application layer (supersession sets the prior version's is_active to
    -- false in the same flow that activates the new one). This table does
    -- not re-enforce it as a hard DB constraint because detecting a
    -- violation of that invariant -- e.g. from an application bug, a partial
    -- write, or manual tampering -- is one of the frozen H0.4 reconciliation
    -- requirements (MULTIPLE_ACTIVE_VERSIONS). A hard constraint here would
    -- make that corrupted state unrepresentable in PostgreSQL and so
    -- undetectable by the auditor.
);

CREATE INDEX document_registry_document_id_idx
    ON public.document_registry (document_id);

CREATE INDEX document_registry_active_idx
    ON public.document_registry (document_id)
    WHERE is_active;
