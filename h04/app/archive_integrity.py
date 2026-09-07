"""H0.4 archived-file integrity checks.

Verifies that the archived file a registry row expects to exist actually
exists at its recorded location, and that its content still hashes to the
registry's SHA-256 document identity. Read-only: this module never writes,
moves, or deletes an archived file or a registry row.
"""

import hashlib
from pathlib import Path


def file_hash(path):
    sha256 = hashlib.sha256()

    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(block)

    return sha256.hexdigest()


def check_archive(row):
    """Check one registry row's archived file.

    Returns None if the archived file exists and its SHA-256 matches the
    registry's document_hash, otherwise a finding dict describing exactly
    one of: MISSING_ARCHIVED_FILE, ARCHIVED_FILE_HASH_MISMATCH.
    """
    path = Path(row["archive_source_location"])

    if not path.is_file():
        return {
            "type": "MISSING_ARCHIVED_FILE",
            "archive_source_location": str(path),
        }

    actual_hash = file_hash(path)

    if actual_hash != row["document_hash"]:
        return {
            "type": "ARCHIVED_FILE_HASH_MISMATCH",
            "archive_source_location": str(path),
            "expected_sha256": row["document_hash"],
            "actual_sha256": actual_hash,
        }

    return None
