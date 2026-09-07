"""H0.4 recovery primitives: Qdrant snapshot, PostgreSQL backup, restore.

These wrap the standard Qdrant snapshot API and Postgres pg_dump/psql, all
targeted only at the isolated containers named in h04/conftest.py (never a
production host or container). Recovered-data integrity is verified by
re-running auditor.run_audit after a restore, not by any bespoke check --
"recovery worked" means the same auditor that detected the corruption now
reports it gone.
"""

import subprocess


def create_qdrant_snapshot(qdrant_client, collection_name):
    """Qdrant snapshot procedure: point-in-time snapshot of one collection."""
    return qdrant_client.create_snapshot(collection_name=collection_name)


def list_qdrant_snapshots(qdrant_client, collection_name):
    return qdrant_client.list_snapshots(collection_name=collection_name)


def recover_qdrant_snapshot(qdrant_client, collection_name, snapshot_name):
    """Controlled restore procedure for Qdrant.

    ``location`` is a file:// URI resolved by the Qdrant *server*, not this
    client -- snapshots created via create_snapshot are written under
    /qdrant/snapshots/<collection_name>/ inside the same container, so a
    same-node restore can reference that path directly.
    """
    location = f"file:///qdrant/snapshots/{collection_name}/{snapshot_name}"
    return qdrant_client.recover_snapshot(
        collection_name=collection_name,
        location=location,
    )


def pg_dump_to_file(container_name, *, db, user, password, dest_path):
    """PostgreSQL backup: pg_dump run inside the isolated container, plain
    SQL written to dest_path on the host."""
    with open(dest_path, "wb") as dest_file:
        subprocess.run(
            [
                "docker", "exec",
                "-e", f"PGPASSWORD={password}",
                container_name,
                "pg_dump", "-U", user, "-d", db, "--format=plain",
                "--clean", "--if-exists",
            ],
            stdout=dest_file,
            check=True,
        )


def verify_backup_file(path):
    """PostgreSQL backup verification: the dump exists, is non-empty, and
    contains the expected table's DDL -- a minimal structural check that
    the backup is usable before it is ever relied on for restore."""
    if not path.is_file() or path.stat().st_size == 0:
        return False
    content = path.read_text(encoding="utf-8", errors="ignore")
    return "document_registry" in content


def pg_restore_from_file(container_name, *, db, user, password, src_path):
    """Controlled restore procedure for PostgreSQL: replay a verified plain
    SQL dump inside the isolated container via psql."""
    with open(src_path, "rb") as src_file:
        subprocess.run(
            [
                "docker", "exec", "-i",
                "-e", f"PGPASSWORD={password}",
                container_name,
                "psql", "-v", "ON_ERROR_STOP=1", "-U", user, "-d", db,
            ],
            stdin=src_file,
            check=True,
        )
