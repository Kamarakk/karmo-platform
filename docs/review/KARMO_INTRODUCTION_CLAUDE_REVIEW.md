# KARMO Introduction — Claude Adversarial Verification Packet

## Scope
Review the KARMO introduction package that connects:

Kamara -> KARMO operator CLI -> model router -> Core registry/dispatcher -> first KarmoLab READ capability -> independent model verification -> evidence returned to Kamara

This package is intentionally bounded. It is meant to make KARMO usable as a local conversational interface without introducing general infrastructure write authority.

## Candidate pinning rule
1. Open the PR whose head branch is `feat/karmo-introduction-operator`.
2. Record the exact PR head SHA before reviewing.
3. Review and test only that exact SHA.
4. If the PR head moves during review, stop and return `NEEDS_VERIFICATION — SHA MOVED`.

## Files expected in scope
- `core-service/core_service/karmolab.py`
- `core-service/core_service/ollama_client.py`
- `core-service/core_service/operator.py`
- `core-service/core_service/__main__.py`
- `core-service/tests/test_operator_activation.py`
- `core-service/deploy/karmo-launcher.sh`
- this review packet

## Required architecture
The candidate must preserve this authority chain:

`Kamara -> KARMO -> controlled models/tools -> Core authority -> bounded READ execution -> independent verification -> evidence`

It must NOT introduce:

`Kamara -> model -> arbitrary shell/network/infrastructure`

or:

`model -> approval/authority`

## Adversarial review checklist

### 1. Operator entry point
Verify:
- `python -m core_service chat` provides a usable local conversational entry point.
- `python -m core_service status` executes one bounded status request.
- existing `python -m core_service health` behavior is not weakened.
- exit/EOF/interrupt handling is safe.
- no inbound network listener is introduced.

Attack:
- empty input
- malformed/unicode input
- attempts to inject shell syntax
- attempts to trick KARMO into write actions
- attempts to embed a command inside a status request

### 2. Model router
Verify:
- production defaults route to local Ollama resources.
- primary and verifier are distinct models.
- model selection does not grant authority.
- a model cannot select an arbitrary tool, command, URL, or executor.
- general chat has no tool execution path.

Attack:
- self-verification
- disabled/missing verifier
- model failure
- malformed model output
- prompt injection asking model to claim write authority

### 3. Ollama boundary
Verify:
- only loopback HTTP is accepted.
- no caller-controlled remote provider URL is available through operator input.
- response size is bounded.
- timeout is bounded.
- model ID validation prevents control-character injection.
- no secret/environment dump is sent to the model.

Attack:
- remote IP URL
- credentials in URL
- path/query/fragment injection
- oversized response
- unavailable Ollama

### 4. KarmoLab READ capability
Verify the first tool is strictly READ-only and bounded to:
- host identity
- CPU count/load
- memory totals/availability
- root filesystem usage
- fixed `systemctl is-active` reads for `karmo-core.service` and `karmo-worker.service`
- fixed `docker ps --format` read

Required invariants:
- subprocess calls use `shell=False`.
- argv is fixed in source and never derived from user/model text.
- no arbitrary filesystem traversal.
- no environment/secret dump.
- no package install, restart, stop/start, network, firewall, database, Qdrant, Ollama mutation, or filesystem write.
- output is bounded.

Attack:
- shell metacharacters in user input
- tool-argument injection
- fake service/container names
- path traversal
- command substitution strings

### 5. Core registry/dispatcher authority
Verify:
- `karmolab.read_status` is registered in the existing `CapabilityRegistry`.
- capability class is `READ`.
- approval requirement is computed by KARMO and remains `NONE` only because the capability is genuinely READ-only.
- execution goes through `CapabilityDispatcher`.
- no alternate direct model-to-handler authority path exists.
- no approval field can be caller/model supplied to lower policy.

### 6. Independent verification
Verify:
- primary model summarizes evidence only.
- verifier is a different model.
- summary is withheld if verifier does not return PASS.
- raw evidence remains available when verification fails or model service is unavailable.
- model verification cannot cause infrastructure mutation.

Attack:
- verifier returns FAIL
- verifier returns malformed output
- primary invents a claim
- model service unavailable

### 7. Write refusal boundary
Verify requests containing infrastructure-changing intent are refused before model/tool execution in activation mode.

Test examples:
- restart worker
- deploy update
- install package
- delete file
- modify network
- patch service

Confirm neither status handler nor model is called for rejected write requests.

### 8. Tests and regressions
Run all applicable suites, including at minimum:

```bash
cd core-service
python3 -m pytest -q
```

Then run the repository’s existing full predeploy/productionization test commands and confirm no previous control-plane, worker, recovery, ticket, approval, registry, or persistence tests regress.

Report exact totals for:
- core-service
- worker-runtime
- worker-service
- core-v2-prototypes
- H0.1
- any other CI jobs

### 9. Deployment readiness
Do NOT deploy during review.

Assess whether the candidate is safe for the separately authorized deployment step that would:
- update `/opt/karmo/core-service` to the approved merged commit
- install a local `/usr/local/bin/karmo` launcher from `core-service/deploy/karmo-launcher.sh`
- verify local Ollama models `qwen3:8b` and `qwen3:4b` are present
- restart only the already-existing `karmo-core.service` if code refresh requires it
- perform health/status/chat smoke tests

No Worker network listener, firewall change, Tailscale change, database migration, Qdrant mutation, secret rotation, or new daemon is part of this activation package.

## Return format

```text
EXACT REVIEWED SHA:
<sha>

SYSTEM-FIT VERDICT:
PROCEED | PROCEED WITH CONSTRAINTS | DEFER | REJECT | NEEDS_VERIFICATION

FINDINGS:
| Severity | File/Area | Finding | Exploit/Failure Path | Required Fix | Status |

TEST RESULTS:
- core-service:
- worker-runtime:
- worker-service:
- core-v2-prototypes:
- H0.1:
- total:

AUTHORITY CHECK:
- model can self-authorize: YES/NO
- arbitrary shell reachable: YES/NO
- arbitrary network destination reachable: YES/NO
- READ tool bypasses dispatcher: YES/NO
- verifier can be same as primary: YES/NO
- write request can execute in activation mode: YES/NO

DEPLOYMENT READINESS:
READY | NOT READY | NEEDS_VERIFICATION

UNRESOLVED:
- BLOCKER:
- HIGH:
- MEDIUM:
- LOW:

FINAL VERDICT:
NOT READY | READY FOR KARMO REVIEW | NEEDS_VERIFICATION
```

Do not return `READY FOR KARMO REVIEW` with any unresolved BLOCKER or HIGH.
Do not merge.
Do not deploy.
Do not access or change production during review.
