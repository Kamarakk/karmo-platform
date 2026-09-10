# KARMO Worker Runtime v0.1 -- Independent Verification Checklist

Run from repo root. All commands are read-only or operate only inside
`worker-runtime/`'s own venv and synthetic fixtures -- nothing here
touches production, installs a large model, or changes network
configuration.

```bash
# 1. Set up the venv (already created this workload; safe to re-run).
cd worker-runtime && python3 -m venv venv && venv/bin/pip install -q pytest

# 2. All tests pass (44 tests: the 24 required scenarios + 20 supporting
#    capability/integration tests).
venv/bin/python -m pytest tests/ -v

# 3. Worker registers.
venv/bin/python -c "
from coordinator import Coordinator
import sys; sys.path.insert(0, 'app')
" 2>/dev/null
venv/bin/python -c "
import sys; sys.path.insert(0, 'app')
from coordinator import Coordinator
c = Coordinator()
r = c.register_worker(worker_id='dev01', hostname='karmo-dev01.local', worker_version='0.1.0',
    platform='Darwin', architecture='arm64', capabilities=[{'capability_id': 'hash_verify'}],
    resource_limits={'cpu': 8, 'memory_mb': 8192})
print('registered:', r.worker_id, r.status.value)
"

# 4. Heartbeat works.
venv/bin/python -c "
import sys; sys.path.insert(0, 'app')
from coordinator import Coordinator
c = Coordinator()
c.register_worker(worker_id='dev01', hostname='h', worker_version='0.1.0', platform='Darwin',
    architecture='arm64', capabilities=[{'capability_id': 'hash_verify'}], resource_limits={})
r = c.heartbeat('dev01')
print('heartbeat status:', r.status.value)
"

# 5. Capabilities advertised (worker record exposes exactly what it registered).
venv/bin/python -c "
import sys; sys.path.insert(0, 'app')
from coordinator import Coordinator
c = Coordinator()
r = c.register_worker(worker_id='dev01', hostname='h', worker_version='0.1.0', platform='Darwin',
    architecture='arm64', capabilities=[{'capability_id': 'hash_verify'}, {'capability_id': 'pytest'}],
    resource_limits={})
print('capabilities:', r.capabilities)
"

# 6. Unauthorized capability is rejected (registering 'ssh' fails).
venv/bin/python -c "
import sys; sys.path.insert(0, 'app')
from coordinator import Coordinator, CoordinatorError
c = Coordinator()
try:
    c.register_worker(worker_id='dev01', hostname='h', worker_version='0.1.0', platform='Darwin',
        architecture='arm64', capabilities=[{'capability_id': 'ssh'}], resource_limits={})
    print('FAIL: ssh capability was accepted')
except CoordinatorError as e:
    print('correctly refused:', e)
"

# 7. Job executes end-to-end (register -> heartbeat -> poll -> execute -> result).
venv/bin/python -c "
import sys; sys.path.insert(0, 'app')
from coordinator import Coordinator
from transport import LocalTransport
from worker_client import WorkerClient
c = Coordinator()
c.register_worker(worker_id='dev01', hostname='h', worker_version='0.1.0', platform='Darwin',
    architecture='arm64', capabilities=[{'capability_id': 'hash_verify'}], resource_limits={})
c.heartbeat('dev01')
c.submit_job(capability_id='hash_verify', payload={'path': 'sample_document.txt'}, idempotency_key='verify-1')
client = WorkerClient(worker_id='dev01', transport=LocalTransport(c),
    allowed_root='tests/fixtures/allowed_workspace')
result = client.poll_and_execute_once(['hash_verify'])
print('job state:', result.state.value, 'sha256:', result.result.output['sha256'])
"

# 8. Path traversal is rejected.
venv/bin/python -c "
import sys; sys.path.insert(0, 'app')
from sandbox import run_capability, PathTraversalError
import capabilities
try:
    run_capability('hash_verify', {'path': '../../../etc/passwd'}, timeout_seconds=30,
        allowed_root='tests/fixtures/allowed_workspace')
    print('FAIL: traversal was allowed')
except PathTraversalError as e:
    print('correctly refused:', e)
"

# 9. Duplicate/replay job submission is idempotent.
venv/bin/python -c "
import sys; sys.path.insert(0, 'app')
from coordinator import Coordinator
c = Coordinator()
j1 = c.submit_job(capability_id='hash_verify', payload={'path': 'x'}, idempotency_key='dup-check')
j2 = c.submit_job(capability_id='hash_verify', payload={'path': 'x'}, idempotency_key='dup-check')
print('same job_id:', j1.job_id == j2.job_id)
"

# 10. Full regression: the reused core-v2 job_model/approval_engine/tool_registry
#     prototypes still pass after this workload's WAITING_FOR_APPROVAL->FAILED fix.
cd ../core-v2-prototypes && venv/bin/python -m pytest -q
```

Expected results are recorded verbatim in `TEST_RESULTS.txt` and
`RUN_SUMMARY.json` in this directory.
