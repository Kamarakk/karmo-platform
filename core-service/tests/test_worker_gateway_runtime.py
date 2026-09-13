import json
import os
from pathlib import Path

import pytest

from core_service.worker_gateway_runtime import (
    WorkerGatewayRuntimeError,
    load_gateway_config,
    validate_gateway_startup,
)


def _write(path: Path, data: str, mode=0o600):
    path.write_text(data)
    path.chmod(mode)
    return str(path)


def _config(tmp_path: Path):
    dsn = _write(tmp_path / "db", "postgresql://example")
    ticket = _write(tmp_path / "ticket", "T" * 48)
    worker = _write(tmp_path / "worker", "W" * 48)
    cfg = {
        "version": 1,
        "database_dsn_file": dsn,
        "ticket_key_id": "core-ticket-v1",
        "ticket_secret_file": ticket,
        "worker_keys": {
            "KARMO-WORKER01": {"key_id": "worker01-v1", "secret_file": worker}
        },
        "max_poll_candidates": 32,
    }
    path = tmp_path / "gateway.json"
    _write(path, json.dumps(cfg))
    return path, cfg


def test_gateway_config_and_secret_material_validate(tmp_path):
    path, _ = _config(tmp_path)
    cfg = load_gateway_config(str(path))
    assert validate_gateway_startup(cfg, expected_worker_id="KARMO-WORKER01") is True


def test_gateway_rejects_unconfigured_forced_identity(tmp_path):
    path, _ = _config(tmp_path)
    cfg = load_gateway_config(str(path))
    with pytest.raises(WorkerGatewayRuntimeError, match="forced worker identity"):
        validate_gateway_startup(cfg, expected_worker_id="KARMO-WORKER02")


def test_gateway_rejects_group_world_readable_secret(tmp_path):
    path, cfg = _config(tmp_path)
    Path(cfg["worker_keys"]["KARMO-WORKER01"]["secret_file"]).chmod(0o644)
    loaded = load_gateway_config(str(path))
    with pytest.raises(WorkerGatewayRuntimeError, match="permissions"):
        validate_gateway_startup(loaded, expected_worker_id="KARMO-WORKER01")


def test_gateway_rejects_symlink_config(tmp_path):
    path, _ = _config(tmp_path)
    link = tmp_path / "gateway-link.json"
    link.symlink_to(path)
    with pytest.raises(WorkerGatewayRuntimeError, match="non-symlink"):
        load_gateway_config(str(link))


def test_gateway_rejects_duplicate_key_ids(tmp_path):
    path, cfg = _config(tmp_path)
    cfg["worker_keys"]["KARMO-WORKER01"]["key_id"] = cfg["ticket_key_id"]
    _write(path, json.dumps(cfg))
    with pytest.raises(WorkerGatewayRuntimeError, match="duplicate key id"):
        load_gateway_config(str(path))


def test_forced_command_launcher_has_fixed_python_entrypoint_and_no_forwarding_logic():
    text = Path("deploy/karmo-worker-gateway").read_text()
    assert "core_service.worker_gateway_runtime" in text
    assert "exec /usr/bin/python3" in text
    assert "eval " not in text
    assert "ssh " not in text
    assert "$@" not in text
