import pytest

from commander_readonly import bounded_text_read, directory_list, service_status
from sandbox import SandboxError, PathTraversalError


def test_text_read_within_allowed_root(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    (allowed / "note.txt").write_text("hello", encoding="utf-8")
    output, _, _ = bounded_text_read(
        {"path": "note.txt"}, sandbox_root=tmp_path, allowed_root=allowed, timeout_seconds=5
    )
    assert output["text"] == "hello"
    assert output["bytes"] == 5


def test_text_read_refuses_parent_escape(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    (tmp_path / "outside.txt").write_text("outside", encoding="utf-8")
    with pytest.raises(PathTraversalError):
        bounded_text_read(
            {"path": "../outside.txt"}, sandbox_root=tmp_path, allowed_root=allowed, timeout_seconds=5
        )


def test_text_read_refuses_oversized_file(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    (allowed / "large.txt").write_bytes(b"x" * (32 * 1024 + 1))
    with pytest.raises(SandboxError, match="32 KiB"):
        bounded_text_read(
            {"path": "large.txt"}, sandbox_root=tmp_path, allowed_root=allowed, timeout_seconds=5
        )


def test_directory_list_is_capped(tmp_path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    for i in range(250):
        (allowed / f"f{i:03}.txt").write_text("x", encoding="utf-8")
    output, _, _ = directory_list(
        {"path": "."}, sandbox_root=tmp_path, allowed_root=allowed, timeout_seconds=5
    )
    assert output["count"] == 200


def test_service_status_refuses_unlisted_unit(tmp_path):
    with pytest.raises(SandboxError, match="allowlist"):
        service_status(
            {"service": "example.service"}, sandbox_root=tmp_path, allowed_root=None, timeout_seconds=5
        )
