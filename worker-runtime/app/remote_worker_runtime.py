"""Production runner for outbound-only KARMO workers.

The worker opens no listener. It validates local configuration, SSH host-key
pinning, and secret-file permissions before creating the existing restricted
SSH/stdio transport and remote-worker client.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path

from capability_manifest import get_canonical_capability
from crypto_boundary import KeyResolver, ResultAuthenticator, WorkerAuthenticator
from ssh_stdio_transport import SshStdioConfig, SshStdioTransport
from ssh_worker_client import RemoteWorkerConfig, SshRemoteWorkerClient


class RemoteWorkerRuntimeError(RuntimeError):
    pass


def _lstat_regular(path: str):
    p = Path(path)
    if not p.is_absolute():
        raise RemoteWorkerRuntimeError("runtime file path must be absolute")
    try:
        st = os.lstat(p)
    except OSError as exc:
        raise RemoteWorkerRuntimeError("required runtime file is unavailable") from exc
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise RemoteWorkerRuntimeError("runtime file must be a regular non-symlink")
    return p, st


def _read_bounded(path: str, *, max_bytes: int = 65536) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        try:
            raw = os.read(fd, max_bytes + 1)
        finally:
            os.close(fd)
    except OSError as exc:
        raise RemoteWorkerRuntimeError("runtime file could not be read") from exc
    if len(raw) > max_bytes:
        raise RemoteWorkerRuntimeError("runtime file exceeds size bound")
    return raw


def _require_mode_owner(path: str, *, owner_uid: int, group_gid: int | None,
                        allowed_modes: set[int]) -> bytes:
    _, st = _lstat_regular(path)
    if st.st_uid != owner_uid:
        raise RemoteWorkerRuntimeError("runtime file owner mismatch")
    if group_gid is not None and st.st_gid != group_gid:
        raise RemoteWorkerRuntimeError("runtime file group mismatch")
    if stat.S_IMODE(st.st_mode) not in allowed_modes:
        raise RemoteWorkerRuntimeError("runtime file permissions are not allowed")
    return _read_bounded(path)


@dataclass(frozen=True)
class WorkerRuntimeConfig:
    worker_id: str
    key_id: str
    ai01_host: str
    ai01_user: str
    identity_file: str
    known_hosts_file: str
    worker_key_file: str
    capabilities: dict[str, str]
    timeout_seconds: int = 30
    poll_interval_seconds: int = 5
    heartbeat_lease_seconds: int = 90

    def validate(self) -> None:
        if not self.worker_id or not self.key_id:
            raise RemoteWorkerRuntimeError("worker identity is required")
        if not self.ai01_host or not self.ai01_user:
            raise RemoteWorkerRuntimeError("AI01 SSH target is required")
        if not isinstance(self.capabilities, dict) or not self.capabilities:
            raise RemoteWorkerRuntimeError("at least one bounded capability is required")
        for capability_id, version in self.capabilities.items():
            if not isinstance(capability_id, str) or not isinstance(version, str):
                raise RemoteWorkerRuntimeError("capability id/version must be strings")
            try:
                canonical = get_canonical_capability(capability_id)
            except Exception as exc:
                raise RemoteWorkerRuntimeError("configured capability is not canonical") from exc
            if version != canonical["version"]:
                raise RemoteWorkerRuntimeError("configured capability version mismatch")
            if canonical["network_required"] or canonical["secrets_required"]:
                raise RemoteWorkerRuntimeError("configured capability exceeds remote worker boundary")
        if not 1 <= int(self.timeout_seconds) <= 300:
            raise RemoteWorkerRuntimeError("execution timeout out of bounds")
        if not 1 <= int(self.poll_interval_seconds) <= 60:
            raise RemoteWorkerRuntimeError("poll interval out of bounds")
        if not 30 <= int(self.heartbeat_lease_seconds) <= 300:
            raise RemoteWorkerRuntimeError("heartbeat lease out of bounds")
        for path in (self.identity_file, self.known_hosts_file, self.worker_key_file):
            if not Path(path).is_absolute():
                raise RemoteWorkerRuntimeError("runtime paths must be absolute")


def load_worker_config(path: str, *, production_permissions: bool = False) -> WorkerRuntimeConfig:
    if production_permissions:
        raw = _require_mode_owner(path, owner_uid=0, group_gid=os.getegid(), allowed_modes={0o640})
    else:
        raw = _require_mode_owner(path, owner_uid=os.geteuid(), group_gid=os.getegid(), allowed_modes={0o600, 0o640})
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RemoteWorkerRuntimeError("worker config is invalid") from exc
    required = {"version", "worker_id", "key_id", "ai01_host", "ai01_user",
                "identity_file", "known_hosts_file", "worker_key_file", "capabilities",
                "timeout_seconds", "poll_interval_seconds", "heartbeat_lease_seconds"}
    if not isinstance(value, dict) or set(value) != required or value.get("version") != 1:
        raise RemoteWorkerRuntimeError("worker config schema mismatch")
    cfg = WorkerRuntimeConfig(
        worker_id=value["worker_id"], key_id=value["key_id"], ai01_host=value["ai01_host"],
        ai01_user=value["ai01_user"], identity_file=value["identity_file"],
        known_hosts_file=value["known_hosts_file"], worker_key_file=value["worker_key_file"],
        capabilities=value["capabilities"], timeout_seconds=int(value["timeout_seconds"]),
        poll_interval_seconds=int(value["poll_interval_seconds"]),
        heartbeat_lease_seconds=int(value["heartbeat_lease_seconds"]),
    )
    cfg.validate()
    return cfg


def _validate_known_hosts(cfg: WorkerRuntimeConfig, *, production_permissions: bool) -> None:
    _, st = _lstat_regular(cfg.known_hosts_file)
    mode = stat.S_IMODE(st.st_mode)
    if mode & 0o022:
        raise RemoteWorkerRuntimeError("known_hosts must not be group/world writable")
    if production_permissions and st.st_uid != 0:
        raise RemoteWorkerRuntimeError("known_hosts must be root-owned")
    lines = _read_bounded(cfg.known_hosts_file).decode("utf-8").splitlines()
    targets = {cfg.ai01_host, f"[{cfg.ai01_host}]:22"}
    found = False
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("@"):
            continue
        fields = line.split()
        if len(fields) >= 3 and any(host in targets for host in fields[0].split(",")):
            found = True
            break
    if not found:
        raise RemoteWorkerRuntimeError("known_hosts does not contain the configured AI01 host pin")


def validate_worker_startup(cfg: WorkerRuntimeConfig, *, production_permissions: bool = False) -> bytes:
    if production_permissions:
        _require_mode_owner(cfg.identity_file, owner_uid=os.geteuid(), group_gid=os.getegid(), allowed_modes={0o600})
        secret = _require_mode_owner(cfg.worker_key_file, owner_uid=0, group_gid=os.getegid(), allowed_modes={0o640}).strip()
    else:
        _require_mode_owner(cfg.identity_file, owner_uid=os.geteuid(), group_gid=os.getegid(), allowed_modes={0o600})
        secret = _require_mode_owner(cfg.worker_key_file, owner_uid=os.geteuid(), group_gid=os.getegid(), allowed_modes={0o600, 0o640}).strip()
    if len(secret) < 32 or b"\x00" in secret:
        raise RemoteWorkerRuntimeError("worker key material is missing or invalid")
    _validate_known_hosts(cfg, production_permissions=production_permissions)
    return secret


def build_client(cfg: WorkerRuntimeConfig, *, production_permissions: bool = False):
    secret = validate_worker_startup(cfg, production_permissions=production_permissions)
    keys = KeyResolver(lambda key_id: secret if key_id == cfg.key_id else None)
    worker_auth = WorkerAuthenticator(keys)
    result_auth = ResultAuthenticator(keys)
    transport = SshStdioTransport(SshStdioConfig(
        host=cfg.ai01_host, user=cfg.ai01_user, identity_file=cfg.identity_file,
        known_hosts_file=cfg.known_hosts_file, connect_timeout_seconds=10,
        request_timeout_seconds=30,
    ))
    remote_cfg = RemoteWorkerConfig(
        worker_id=cfg.worker_id, key_id=cfg.key_id,
        capability_versions=cfg.capabilities, timeout_seconds=cfg.timeout_seconds,
    )
    return SshRemoteWorkerClient(
        config=remote_cfg, transport=transport,
        credential_provider=lambda: worker_auth.issue(
            worker_id=cfg.worker_id, key_id=cfg.key_id, ttl_seconds=120
        ),
        result_authenticator=result_auth,
    )


def run_once(cfg: WorkerRuntimeConfig, *, production_permissions: bool = False):
    client = build_client(cfg, production_permissions=production_permissions)
    client.heartbeat(lease_seconds=cfg.heartbeat_lease_seconds)
    return client.poll_once()


def run_loop(cfg: WorkerRuntimeConfig, *, production_permissions: bool = False) -> int:
    client = build_client(cfg, production_permissions=production_permissions)
    while True:
        try:
            client.heartbeat(lease_seconds=cfg.heartbeat_lease_seconds)
            client.poll_once()
            time.sleep(cfg.poll_interval_seconds)
        except KeyboardInterrupt:
            return 0
        except Exception:
            time.sleep(min(30, max(5, cfg.poll_interval_seconds)))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--check-config", action="store_true")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    cfg = load_worker_config(args.config, production_permissions=True)
    validate_worker_startup(cfg, production_permissions=True)
    if args.check_config:
        return 0
    if args.once:
        run_once(cfg, production_permissions=True)
        return 0
    return run_loop(cfg, production_permissions=True)


if __name__ == "__main__":
    raise SystemExit(main())
