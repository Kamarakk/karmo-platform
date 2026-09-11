# KARMO Access & Connection Registry

Purpose: durable, machine-readable access knowledge for humans and authorized agents. This directory records how KARMO systems are identified, reached, authenticated, recovered, and verified without storing secrets.

## Read order
1. `HOST_ACCESS_REGISTRY.yaml`
2. `CONNECTION_PATHS.yaml`
3. `AUTH_METHOD_REGISTRY.yaml`
4. `ACCESS_RECOVERY.md`
5. Relevant host/runbook documentation

## Rules
- Resolve the connection context before recommending an IP or route: HOME, OFFICE, TRAVEL_REMOTE, LOCAL_CONSOLE, or AGENT_REMOTE.
- Separate routing, transport, authentication, authorization, and privilege. A timeout is not evidence of a bad password or key.
- Prefer an existing verified tool/path before introducing new software.
- Never store passwords, private keys, tokens, recovery codes, or API secrets in this repository. Store only references to approved credential mechanisms.
- Every access fact must carry a status: VERIFIED, HISTORICAL, NEEDS_VERIFICATION, or RETIRED, plus a last-verified date where known.
- Reaching a production host does not grant authority to modify it. Production changes still require the governance authorization gate.
- Before changing access architecture, run the Mandatory System-Fit Review in `docs/governance/KARMO_SYSTEM_FIT_REVIEW.md`.

## Design intent
This registry is not just an IP list. It is the durable access decision layer for ChatGPT, Claude Code, Codex, future KARMO agents, and human operators. It should answer: what is the target, where is the operator, which route applies, which identity/auth method is expected, what privilege is required, what is the fallback, and how fresh is the information?
