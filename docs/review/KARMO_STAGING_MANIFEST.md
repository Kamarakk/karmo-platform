# KARMO Staging Manifest

Candidate branch: `staging/karmo-full-predeploy-20260912`

## Core

- `core-service/core_service/registry.py`
- `core-service/core_service/task_state.py`
- `core-service/core_service/model_router.py`
- `core-service/core_service/verification.py`
- `core-service/core_service/dispatcher.py`
- `core-service/core_service/persistence.py`
- `core-service/core_service/migrations/001_core_v2_substrate.sql`
- `core-service/tests/test_core_v2_staging.py`

## Worker hardening

- `worker-runtime/app/crypto_boundary.py`
- `worker-runtime/app/capabilities.py` environment allowlisting change
- `worker-runtime/tests/test_predeploy_security_hardening.py`

## Validation

- `.github/workflows/karmo-full-predeploy.yml`

## Review / handoff

- `STAGING_KARMO_FULL_PREDEPLOY.md`
- `docs/review/README.md`
- `docs/review/KARMO_PREDEPLOY_STATUS.md`
- `docs/review/KARMO_PREDEPLOY_REVIEW_CHECKLIST.md`
- `docs/review/KARMO_PREDEPLOY_DEPLOYMENT_TEMPLATE.md`
- `docs/review/KARMO_CLAUDE_REVIEW_PROMPT.md`
- `docs/review/KARMO_REVIEW_PROMPT.md`
- `docs/review/KARMO_NEXT_AGENT_FRENZY.md`
- `docs/review/KARMO_MORNING_GATE.md`

This manifest is descriptive only. Presence on this branch is not approval to merge or deploy.
