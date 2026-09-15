"""Production wiring for the restricted KARMO worker SSH/stdio gateway.

No listener is opened here. sshd invokes this process only through a per-key
forced command. Configuration and key material are read from fixed local files
and are rejected when ownership, type, or permissions are unsafe.
"""
from __future__ import annotations

import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from .worker_coordination import PostgresWorkerCoordinatorStore, WorkerCoordinator
from .worker_gateway_backend import PostgresWorkerGatewayBackend
from .worker_gateway_forced_command import serve_forced_command


class WorkerGatewayRuntimeError(RuntimeError):
    pass


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_DEFAULT_CONFIG = "/etc/karmo/worker-gateway.json"


def _secure_read(path: str, *, owner_uid: int, group_gid: int | None,
                 allowed_modes: set[int], max_bytes: int = 65536) -> bytes:
    p = Path(path)
    if not p.is_absolute():
        raise WorkerGatewayRuntimeError("secure file path must be absolute")
    try:
        st = os.lstat(p)
    except OSError as exc:
        raise WorkerGatewayRuntimeError("required secure file is unavailable") from exc
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise WorkerGatewayRuntimeError("secure file must be a regular non-symlink")
    if st.st_uid != owner_uid:
        raise WorkerGatewayRuntimeError("secure file owner mismatch")
    if group_gid is not None and st.st_gid != group_gid:
        raise WorkerGatewayRuntimeError("secure file group mismatch")
    mode = stat.S_IMODE(st.st_mode)
    if mode not in allowed_modes:
        raise WorkerGatewayRuntimeError("secure file permissions are not allowed")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(p, flags)
        try:
            data = os.read(fd, max_bytes + 1)
        finally:
            os.close(fd)
    except OSError as exc:
        raise WorkerGatewayRuntimeError("secure file could not be read") from exc
    if len(data) > max_bytes:
        raise WorkerGatewayRuntimeError("secure file exceeds size bound")
    return data


@dataclass(frozen=True)
class GatewayRuntimeConfig:
    database_dsn_file: str
    ticket_key_id: str
    ticket_secret_file: str
    worker_keys: dict[str, dict[str, str]]
    max_poll_candidates: int
    owner_uid: int
    group_gid: int | None
    allowed_modes: frozenset[int]

    def validate(self) -> None:
        if not _SAFE_ID.fullmatch(self.ticket_key_id):
            raise WorkerGatewayRuntimeError("invalid ticket key id")
        if not self.worker_keys:
            raise WorkerGatewayRuntimeError("at least one worker key is required")
        seen = {self.ticket_key_id}
        for worker_id, entry in self.worker_keys.items():
            if not _SAFE_ID.fullmatch(worker_id):
                raise WorkerGatewayRuntimeError("invalid worker id")
            if set(entry) != {"key_id", "secret_file"}:
                raise WorkerGatewayRuntimeError("invalid worker key schema")
            key_id = entry["key_id"]
            if not _SAFE_ID.fullmatch(key_id) or key_id in seen:
                raise WorkerGatewayRuntimeError("invalid or duplicate key id")
            seen.add(key_id)
            if not Path(entry["secret_file"]).is_absolute():
                raise WorkerGatewayRuntimeError("worker secret path must be absolute")
        if not Path(self.database_dsn_file).is_absolute() or not Path(self.ticket_secret_file).is_absolute():
            raise WorkerGatewayRuntimeError("gateway secret paths must be absolute")
        if not 1 <= int(self.max_poll_candidates) <= 128:
            raise WorkerGatewayRuntimeError("max_poll_candidates out of bounds")


def load_gateway_config(path: str, *, production_permissions: bool = False) -> GatewayRuntimeConfig:
    if production_permissions:
        owner_uid, group_gid, modes = 0, os.getegid(), {0o640}
    else:
        owner_uid, group_gid, modes = os.geteuid(), os.getegid(), {0o600, 0o640}
    raw = _secure_read(path, owner_uid=owner_uid, group_gid=group_gid,
                       allowed_modes=modes)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerGatewayRuntimeError("gateway config is invalid") from exc
    required = {"version", "database_dsn_file", "ticket_key_id", "ticket_secret_file",
                "worker_keys", "max_poll_candidates"}
    if not isinstance(value, dict) or set(value) != required or value.get("version") != 1:
        raise WorkerGatewayRuntimeError("gateway config schema mismatch")
    cfg = GatewayRuntimeConfig(
        database_dsn_file=value["database_dsn_file"], ticket_key_id=value["ticket_key_id"],
        ticket_secret_file=value["ticket_secret_file"], worker_keys=value["worker_keys"],
        max_poll_candidates=int(value["max_poll_candidates"]), owner_uid=owner_uid,
        group_gid=group_gid, allowed_modes=frozenset(modes),
    )
    cfg.validate()
    return cfg


def _read_text_secret(cfg: GatewayRuntimeConfig, path: str, *, minimum_bytes: int = 1) -> str:
    raw = _secure_read(path, owner_uid=cfg.owner_uid, group_gid=cfg.group_gid,
                       allowed_modes=set(cfg.allowed_modes), max_bytes=8192).strip()
    if len(raw) < minimum_bytes or b"\x00" in raw:
        raise WorkerGatewayRuntimeError("secret material is missing or invalid")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WorkerGatewayRuntimeError("secret material encoding is invalid") from exc


def validate_gateway_startup(cfg: GatewayRuntimeConfig, *, expected_worker_id: str | None = None) -> bool:
    if expected_worker_id is not None and expected_worker_id not in cfg.worker_keys:
        raise WorkerGatewayRuntimeError("forced worker identity is not configured")
    _read_text_secret(cfg, cfg.database_dsn_file)
    _read_text_secret(cfg, cfg.ticket_secret_file, minimum_bytes=32)
    for entry in cfg.worker_keys.values():
        _read_text_secret(cfg, entry["secret_file"], minimum_bytes=32)
    return True


def build_backend(cfg: GatewayRuntimeConfig):
    validate_gateway_startup(cfg)
    try:
        import psycopg
        from crypto_boundary import ExecutionTicketAuthority, KeyResolver, ResultAuthenticator, WorkerAuthenticator
    except ImportError as exc:
        raise WorkerGatewayRuntimeError("gateway runtime dependency unavailable") from exc

    dsn = _read_text_secret(cfg, cfg.database_dsn_file)
    secrets_by_id = {
        cfg.ticket_key_id: _read_text_secret(cfg, cfg.ticket_secret_file, minimum_bytes=32).encode(),
    }
    for entry in cfg.worker_keys.values():
        secrets_by_id[entry["key_id"]] = _read_text_secret(
            cfg, entry["secret_file"], minimum_bytes=32
        ).encode()

    keys = KeyResolver(lambda key_id: secrets_by_id.get(key_id))
    worker_auth = WorkerAuthenticator(keys)
    ticket_auth = ExecutionTicketAuthority(keys, signing_key_id=cfg.ticket_key_id)
    result_auth = ResultAuthenticator(keys)

    def connection_factory():
        return psycopg.connect(dsn)

    store = PostgresWorkerCoordinatorStore(connection_factory)
    coordinator = WorkerCoordinator(
        store, worker_authenticator=worker_auth,
        ticket_authority=ticket_auth, result_authenticator=result_auth,
    )
    return PostgresWorkerGatewayBackend(
        store=store, coordinator=coordinator, connection_factory=connection_factory,
        max_poll_candidates=cfg.max_poll_candidates,
    )


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) == 2 and argv[0] == "--check-config":
        cfg = load_gateway_config(argv[1], production_permissions=True)
        validate_gateway_startup(cfg)
        return 0
    if len(argv) != 1 or not _SAFE_ID.fullmatch(argv[0]):
        raise WorkerGatewayRuntimeError("exactly one forced worker identity is required")
    worker_id = argv[0]
    cfg = load_gateway_config(_DEFAULT_CONFIG, production_permissions=True)
    validate_gateway_startup(cfg, expected_worker_id=worker_id)
    backend = build_backend(cfg)
    return serve_forced_command(backend=backend, expected_worker_id=worker_id)


if __name__ == "__main__":
    raise SystemExit(main())
