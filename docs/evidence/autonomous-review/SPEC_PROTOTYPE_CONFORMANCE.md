# Spec/Design ↔ Prototype Conformance

Compares `docs/architecture/KARMO_CORE_V2_SPECIFICATION.md` and its
component design docs against the actual code in `core-v2-prototypes/`.
**No documentation claims implementation where only design exists** —
this table exists specifically to verify that and correct it if false.

| Requirement | Status | Note |
|---|---|---|
| Tool identity (namespaced `tool_id`) | IMPLEMENTED / TESTED | `tool_registry/registry.py` |
| Full manifest schema, all fields required | IMPLEMENTED / TESTED | per-field refusal tests |
| I-09 5-tier `capability_class` | IMPLEMENTED / TESTED | reused verbatim, not redefined |
| Computed (never declarable) approval requirement | IMPLEMENTED / TESTED | full combinatorial matrix |
| `financial_action`/`destructive_action` force floor | IMPLEMENTED / TESTED | |
| Unknown-field rejection (closed schema) | IMPLEMENTED / TESTED | added by this review |
| `public.tool_registry` persistent table | **NOT IMPLEMENTED** | prototype uses an in-memory dict; the design doc's PostgreSQL table was never built |
| `public.tool_invocation_ledger` | **NOT IMPLEMENTED** | no ledger code exists anywhere in `core-v2-prototypes/` — the Approval Engine's own `audit_trail` is a different, narrower thing (per-approval history, not a cross-tool invocation log) |
| Report-only registry auditor (registry vs. ledger) | **NOT IMPLEMENTED** | no code — the ledger it would reconcile against doesn't exist either |
| Shared dispatcher (single enforced call path) | **PARTIAL** | see "Integration gap" below |
| Domain-scoped credential isolation (`failure_isolation`) | **PARTIAL** | a required manifest *description* field only; nothing in the prototype code enforces it at runtime |
| Deprecation lifecycle (append-only, `superseded_by`) | IMPLEMENTED / TESTED | |
| Approval Engine: 7-state machine | IMPLEMENTED / TESTED | including full negative-transition coverage |
| Arguments-digest binding | IMPLEMENTED / TESTED | |
| Single-use / no replay | IMPLEMENTED / TESTED | |
| Executor-identity binding | IMPLEMENTED / TESTED | added by this review (Finding 3) |
| `public.approval_ledger` persistent table | **NOT IMPLEMENTED** | in-memory only, same caveat as the tool registry |
| Job/Event model: 7-state machine | IMPLEMENTED / TESTED | |
| Deterministic identity, idempotent submission | IMPLEMENTED / TESTED | |
| Claim-token crash/restart recovery | IMPLEMENTED / TESTED | reuses H0.1 outbox pattern directly |
| Full scheduler (timers, priority, background loop) | INTENTIONALLY DEFERRED | explicit instruction: "not a full scheduler" |
| Configuration single-sourcing accessor | IMPLEMENTED / TESTED | isolated POC |
| Wired into any real existing KARMO file | INTENTIONALLY DEFERRED | explicit instruction: prototype must not change existing runtime behavior |
| Failure-injection: all 12 named categories | IMPLEMENTED / TESTED | applied against the Approval Engine and Job Model prototypes |
| Failure injection against real Postgres/Qdrant/network | INTENTIONALLY DEFERRED | explicit instruction: synthetic only |
| Observability (structured logs, metrics, correlation IDs) | **NOT IMPLEMENTED** | design-only, correctly represented as such by PR #18 — no prototype emits structured logs or correlation IDs anywhere |
| Monitoring software (Prometheus/Grafana/etc.) | INTENTIONALLY DEFERRED | explicit instruction: none installed |
| Security threat-model mitigations requiring code (SSRF allowlist, path-traversal guards) | **NOT IMPLEMENTED** | no dispatcher exists yet for these to attach to |
| Secret handling (reference-only, never logged) | IMPLEMENTED / TESTED | `config_poc/config.py` |
| Autonomous-run evidence schema | IMPLEMENTED / TESTED | |
| Independent verifier (evidence/commit/PR/manifest checks) | IMPLEMENTED / TESTED | evidence/test_results check added by this review (Finding 1) |
| Trust Score, never grants permissions | IMPLEMENTED / TESTED | placeholder components fixed by this review (Finding 2) |
| Real git/`gh` subprocess integration for the verifier | INTENTIONALLY DEFERRED | design doc itself states ground-truth sources are injected callables; a future real tool supplies real implementations |
| Consolidated Core v2 spec: EXISTING/PROPOSED/FUTURE separation | IMPLEMENTED (as documentation) | accurate as of this review, now with corrected test counts |

## Integration gap (the most significant PARTIAL finding)

**The Tool Registry and Approval Engine prototypes were never actually
wired together in any test.** Every test that uses the Approval Engine
passes `authority_class` as a **hardcoded string literal**
(`"REVERSIBLE_WRITE"`, `"DESTRUCTIVE_HIGH_IMPACT"`) rather than deriving
it from an actual `tool_registry.get(tool_id).computed_approval_requirement`
lookup. This means the end-to-end flow the architecture document
describes — register a tool, compute its authority, request an approval
bound to that computed authority, execute only after a matching approval
— has never been exercised as one connected path. Each component
independently proves its own half correctly; **the glue between them (the
"shared dispatcher" the architecture document names as Workstream 3
Phase C) does not exist as code, and is not claimed to** — but this table
makes explicit what was previously only implicit in the architecture
doc's own "not implemented tonight" section, so no reader mistakes
"two components exist" for "the components work together."

## Summary

23 requirements checked: **15 IMPLEMENTED/TESTED**, **4 NOT IMPLEMENTED**
(persistent storage for both prototypes, the ledger, the report-only
auditor, observability, and security-mitigation code — all correctly
already described as future work in the design docs, not falsely claimed
otherwise), **2 PARTIAL** (the dispatcher/integration gap and
failure-isolation enforcement), **rest INTENTIONALLY DEFERRED** per
explicit program instructions. No documentation reviewed this session
claims implementation where only design exists.
