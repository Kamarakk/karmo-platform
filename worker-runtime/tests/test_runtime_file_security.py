import json
from pathlib import Path

import pytest

from remote_worker_runtime import RemoteWorkerRuntimeError, load_worker_config, validate_worker_startup


def _put(path, text, mode=0o600):
    path.write_text(text)
    path.chmod(mode)
    return str(path)


def _fixture(tmp_path):
    identity = _put(tmp_path / "identity", "x")
    hosts = _put(tmp_path / "hosts", "192.168.1.235 ssh-ed25519 x\n")
    material = _put(tmp_path / "material", "x" * 48)
    value = {
        "version": 1,
        "worker_id": "KARMO-WORKER01",
        "key_id": "worker01-v1",
        "ai01_host": "192.168.1.235",
        "ai01_user": "karmo-gateway",
        "identity_file": identity,
        "known_hosts_file": hosts,
        "worker_key_file": material,
        "capabilities": {"local_model_probe": "1.0.0"},
        "timeout_seconds": 30,
        "poll_interval_seconds": 5,
        "heartbeat_lease_seconds": 90,
    }
    cfg = tmp_path / "worker.json"
    _put(cfg, json.dumps(value))
    return cfg, value


def test_startup_rejects_missing_host_pin(tmp_path):
    path, value = _fixture(tmp_path)
    Path(value["known_hosts_file"]).write_text("192.168.1.99 ssh-ed25519 x\n")
    cfg = load_worker_config(str(path))
    with pytest.raises(RemoteWorkerRuntimeError, match="host pin"):
        validate_worker_startup(cfg)


def test_startup_rejects_overpermissive_identity(tmp_path):
    path, value = _fixture(tmp_path)
    Path(value["identity_file"]).chmod(0o644)
    cfg = load_worker_config(str(path))
    with pytest.raises(RemoteWorkerRuntimeError, match="permissions"):
        validate_worker_startup(cfg)


def test_startup_rejects_symlink_material(tmp_path):
    path, value = _fixture(tmp_path)
    link = tmp_path / "linked"
    link.symlink_to(value["worker_key_file"])
    raw = json.loads(path.read_text())
    raw["worker_key_file"] = str(link)
    _put(path, json.dumps(raw))
    cfg = load_worker_config(str(path))
    with pytest.raises(RemoteWorkerRuntimeError, match="non-symlink"):
        validate_worker_startup(cfg)
