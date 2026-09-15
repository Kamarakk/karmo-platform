from pathlib import Path

import pytest

from remote_worker_runtime import RemoteWorkerRuntimeError, WorkerRuntimeConfig


def test_runtime_config_requires_absolute_paths():
    cfg = WorkerRuntimeConfig(
        worker_id="KARMO-WORKER01",
        key_id="worker01-v1",
        ai01_host="192.168.1.235",
        ai01_user="karmo-gateway",
        identity_file="relative-id",
        known_hosts_file="/etc/karmo/known_hosts",
        worker_key_file="/etc/karmo/worker-key",
        capabilities={"local_model_probe": "1.0.0"},
    )
    with pytest.raises(RemoteWorkerRuntimeError, match="absolute"):
        cfg.validate()


def test_runtime_config_bounds_polling_and_heartbeat():
    cfg = WorkerRuntimeConfig(
        worker_id="KARMO-WORKER01",
        key_id="worker01-v1",
        ai01_host="192.168.1.235",
        ai01_user="karmo-gateway",
        identity_file="/etc/karmo/id",
        known_hosts_file="/etc/karmo/known_hosts",
        worker_key_file="/etc/karmo/worker-key",
        capabilities={"local_model_probe": "1.0.0"},
        poll_interval_seconds=0,
    )
    with pytest.raises(RemoteWorkerRuntimeError, match="poll interval"):
        cfg.validate()


def test_runtime_config_rejects_unknown_or_wrong_version_capabilities():
    base = dict(
        worker_id="KARMO-WORKER01",
        key_id="worker01-v1",
        ai01_host="192.168.1.235",
        ai01_user="karmo-gateway",
        identity_file="/etc/karmo/id",
        known_hosts_file="/etc/karmo/known_hosts",
        worker_key_file="/etc/karmo/worker-key",
    )
    with pytest.raises(RemoteWorkerRuntimeError, match="not canonical"):
        WorkerRuntimeConfig(**base, capabilities={"invented": "1"}).validate()
    with pytest.raises(RemoteWorkerRuntimeError, match="version mismatch"):
        WorkerRuntimeConfig(**base, capabilities={"local_model_probe": "9"}).validate()


def test_worker_service_templates_are_outbound_polling_only_and_hardened():
    for name in ("karmo-worker01.service", "karmo-worker02.service"):
        text = Path("deploy", name).read_text()
        for required in (
            "remote_worker_runtime",
            "ExecStartPre=",
            "NoNewPrivileges=true",
            "ProtectSystem=strict",
            "PrivateDevices=true",
            "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6",
            "--check-config",
        ):
            assert required in text
        assert "ListenStream" not in text
        assert "0.0.0.0" not in text
