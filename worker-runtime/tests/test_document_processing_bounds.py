import pytest

from capabilities import MAX_DOCUMENT_BYTES, _document_processing_test
from sandbox import SandboxError


def test_document_processing_refuses_oversized_workspace_file_before_read(tmp_path):
    allowed_root = tmp_path / "workspace"
    allowed_root.mkdir()
    oversized = allowed_root / "oversized.txt"

    # Sparse/truncated creation keeps the regression cheap while proving the
    # handler checks filesystem size before allocating/reading the document.
    with oversized.open("wb") as handle:
        handle.truncate(MAX_DOCUMENT_BYTES + 1)

    with pytest.raises(SandboxError, match="document input is too large"):
        _document_processing_test(
            {"path": "oversized.txt"},
            sandbox_root=tmp_path / "sandbox",
            allowed_root=allowed_root,
            timeout_seconds=5,
        )


def test_document_processing_still_accepts_bounded_file(tmp_path):
    allowed_root = tmp_path / "workspace"
    allowed_root.mkdir()
    document = allowed_root / "small.txt"
    document.write_text("a" * 401, encoding="utf-8")

    output, summary, evidence = _document_processing_test(
        {"path": "small.txt"},
        sandbox_root=tmp_path / "sandbox",
        allowed_root=allowed_root,
        timeout_seconds=5,
    )

    assert output == {"chunk_count": 3, "char_count": 401}
    assert summary == "document_processing_test: 3 synthetic chunk(s)"
    assert evidence == []
