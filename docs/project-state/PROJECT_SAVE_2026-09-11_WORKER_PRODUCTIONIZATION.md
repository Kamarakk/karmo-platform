# PROJECT SAVE — Worker Runtime Productionization

Saved: 2026-09-11
Branch: `feat/worker-runtime-productionization`
PR: #34 — `feat: productionize Worker Runtime behind Core`

## Verified this session

- KARMO-AI01 is reachable through Remote Desktop Commander.
- Core host preflight passed: `/usr/bin/python3` = Python 3.12.3; systemd 255 present; `/opt/karmo/core-service` and `karmo-core.service` absent; `/opt` is root-owned and non-interactive sudo is unavailable.
- PR #33 Core productionization is merged into `main`; targeted Core CI passed before merge.
- Worker host read-only preflight found `/opt/karmo/worker-service` and `karmo-worker.service` absent; no naming/path collision.
- Existing merged `worker-runtime/` still imports `core-v2-prototypes/` directly through `_prototype_paths.py` reuse shims, so it is not safe to copy unchanged into production.
- `transport.py` explicitly remains in-process-only; real worker network transport is still prohibited by the approved rollout.

## Worker productionization work completed

Created `worker-service/` as the restricted production boundary:
- local-only service lifecycle;
- hard dependency on production `core_service` import;
- fail-closed health if Core binding is unavailable;
- no listener or worker network transport;
- no database/Qdrant writes;
- no secrets;
- no capability/job execution yet;
- systemd unit requires `karmo-core.service` and uses explicit production PYTHONPATH;
- targeted tests cover healthy Core binding and fail-closed behavior;
- dedicated GitHub Actions workflow added.

Gate C evidence is recorded at `docs/evidence/worker-runtime/PRODUCTIONIZATION_GATE_C.md`.

## Production status

- Core host deployment: **NOT YET EXECUTED** (privileged install pending).
- Worker host deployment: **NOT YET EXECUTED** and blocked until Core passes its production smoke check.
- Existing KARMO production services/data: **UNCHANGED**.
- PostgreSQL/Qdrant: **UNCHANGED**.
- No secrets changed or exposed.

## Next action

When Kamara is available at a terminal, perform the already-approved privileged Core install under the bounded rollout scope, start only `karmo-core.service`, and perform one smoke check. If Core is healthy, complete Gate C validation for PR #34 and then install/start only the new Worker service with one smoke check.

Do not enable real worker network transport or capability execution in this rollout.
