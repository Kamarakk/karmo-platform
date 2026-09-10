# KARMO Core v2 Security / Threat Model

Status: **DESIGN ONLY. Governance not modified.** Threat-models the
future capability platform (Tool/Capability Registry, Approval Engine,
Job/Event model — Workstreams 3–5, this program), not KARMO as it exists
today (which has no multi-tool surface to attack yet). Produced under the
Core v2 Engineering Blueprint Program, Workstream 8.

For each threat: description, why it matters for Core v2 specifically,
and mitigation — mapped to an existing invariant wherever one already
applies. A governance addition is proposed **only** where genuinely
missing, clearly marked, not adopted.

## Threats

### Prompt-driven tool abuse

An agent (or a compromised/confused upstream model) is talked into
invoking a tool it shouldn't, via crafted input rather than a genuine
user request. **Mitigation**: the Approval Engine (Workstream 4) binds
every above-`NONE`-floor invocation to a specific, argument-hashed,
single-use approval a human actually granted — a prompt cannot forge an
approval it doesn't hold. Maps to I-09 (authority does not follow from
intelligence/plausibility) directly.

### Confused deputy

A low-privilege caller gets a high-privilege tool to act on its behalf by
exploiting the tool's own broader access. **Mitigation**: Workstream 3's
`failure_isolation` requirement (each domain's tools execute within that
domain's own credential/connection scope, never a shared one) plus
per-tool `read_scope`/`write_scope` declarations prevent a tool from
having more reach than its own manifest declares. Maps to I-09's
least-privilege principle.

### Authority escalation

A tool or a chain of tools ends up performing an action above its
declared capability class. **Mitigation**: Workstream 3's core guarantee
— `human_approval_requirement` is *computed*, never independently
settable, and can only be raised by `financial_action`/`destructive_action`,
never lowered. This program's own W3 prototype must include a test
proving this directly (see Workstream 3 below). Maps to I-09.

### Approval spoofing

A caller presents a fabricated or forged approval to bypass the gate.
**Mitigation**: Workstream 4's approval record must be unforgeable in
practice — a durable, server-side-issued `approval_id` plus an arguments
digest computed server-side at grant time, checked byte-for-byte at
execution time; nothing about "looks approved" is trusted without that
record existing in the ledger. No existing invariant names this
specifically — I-09 covers authority broadly; this is an implementation
requirement of the Approval Engine design, not a new invariant.

### Approval replay

A single valid approval is used to authorize the same action twice, or a
different action once the same approval already fired. **Mitigation**:
Workstream 4's explicit design requirement — single-use semantics,
`EXECUTED` is a terminal state, any second execution attempt against the
same `approval_id` is rejected regardless of outcome of the first.
Prototyped and tested directly (Workstream 4).

### Malicious tool registration

A compromised or careless domain module registers a tool with an
under-declared risk profile (e.g. a `destructive_action` tool registered
as `READ`). **Mitigation**: Workstream 3's manifest validation refuses
registration on any missing/inconsistent required field — but this alone
does not *verify* the declared flags are honest (a domain author could
still lie). **Genuine gap**: no existing invariant requires an
independent review of a new tool's manifest before it becomes registrable.
**Proposed governance addition (NOT adopted)**: a lightweight
"Tool Registration Review" requirement — any new manifest with
`financial_action` or `destructive_action` true requires the same kind of
explicit review a production access authorization already requires,
before first registration, not merely before first invocation. This is
Natalie's decision, not implemented or adopted here.

### Schema manipulation

A tool's declared input/output schema is exploited to smuggle unexpected
data (e.g. oversized payloads, unexpected fields consumed downstream).
**Mitigation**: standard JSON Schema validation at the dispatcher
boundary (Workstream 3's shared dispatcher is the *only* call path,
making this a single enforcement point rather than per-tool). Maps to
I-05 (bounded resources) for payload-size bounding specifically.

### Secret exposure

A tool, its logs, or its ledger entry leaks a credential value.
**Mitigation**: already governed by the Mandatory Production Access
Authorization Gate's secret-handling rule (never expose/print/persist a
value; reference existing loading mechanisms) — Workstream 3's manifest
already requires `secret_requirements` be *references*, never values, and
the invocation ledger design explicitly stores an input *hash*, not the
raw payload, specifically to avoid this. Maps directly to I-09 and the
Production Access Authorization Gate; no new invariant needed.

### SSRF (server-side request forgery)

A tool with `network_requirements` is tricked into making a request to an
unintended internal/external target (e.g. a URL passed as a tool
argument, used unchecked). **Mitigation**: Workstream 3's manifest
requires `network_requirements` be declared *at registration time*, not
computed from caller-supplied input — a tool whose network target is
caller-controlled needs an explicit allowlist check at the dispatcher
level. **Genuine gap**: no existing invariant addresses SSRF specifically.
Not proposing a dedicated invariant — this is a standard secure-coding
requirement to enforce in the dispatcher implementation, not a
KARMO-specific governance question.

### Arbitrary command execution

A tool's implementation (or a dependency it calls) allows command
injection from tool arguments. **Mitigation**: standard secure-coding
practice (parameterized calls, no shell interpolation of caller input) —
already the pattern every existing KARMO module follows (e.g.
`registry_db.py`'s parameterized SQL throughout, confirmed by this
session's own code reading). Not a governance gap; an implementation
discipline to carry forward.

### Unsafe file access

A tool with filesystem access (e.g. a future document-ingest-shaped tool)
is tricked into reading/writing outside its intended directory (path
traversal). **Mitigation**: `document_ingest_h04.py`'s existing pattern
(`archive_destination` resolves within a fixed `PROCESSED`/`FAILED` root,
never caller-supplied) is the model to reuse; any Core v2 tool touching
the filesystem should declare its allowed root(s) in its manifest, checked
by the dispatcher, not trusted per-tool.

### Data exfiltration

A tool with read access to sensitive data and any external side effect
(network, posting) could be used to move that data outside KARMO's
control. **Mitigation**: I-09's explicit prohibition — "do not combine
unrelated personal, business, infrastructure, security, or other
sensitive data domains merely because KARMO technically has access to
them" — already covers the *combination* risk. Workstream 3's
domain-scoped `read_scope`/`write_scope` and `failure_isolation` design
directly operationalizes this for the tool registry specifically: a
BloomBoss customer-communication tool cannot read Finance data because
its manifest never grants that scope.

### Compromised external API

A third-party API a tool depends on (broker, social platform, image-gen
service) is itself compromised or returns malicious data. **Mitigation**:
`timeout_seconds`/`retry_policy` bounding (Workstream 3 manifest fields)
plus output-schema validation on the *response* side, not just the
request side — a compromised API returning well-formed-but-wrong data is
a genuine residual risk no schema check alone catches; human review of
consequential outputs (financial proposals, external posts) via the
Approval Engine's "explain reasoning" requirement (Workstream 11) is the
real backstop here, not a technical control.

### Supply-chain dependency

A Python package (or Docling, Ollama, a future broker SDK) is compromised
upstream. **Mitigation**: not a Core v2-specific concern — general
dependency hygiene (pinned versions, e.g. Spec Kit's own `@v1.0.4` pin
already established as the pattern in this repo). No new invariant
proposed; existing practice already models the right behavior.

### Financial-action abuse

Covered exhaustively by Workstream 11 (Finance/Trading Safety Spec) — the
hard floor (`financial_action: true` forces `EXPLICIT_PER_CALL`,
never generic "trade for me" approval, exact-parameter binding) is this
threat's primary mitigation, already required by
`docs/vision/KARMO_PRODUCT_VISION.md`'s standing constraint and this
program's own explicit instruction.

### Social-media / account abuse

An external-posting tool is invoked with content that damages the
account's reputation or violates a platform's terms, even if technically
"approved." **Mitigation**: the Approval Engine's "explain reasoning"
requirement applies here too — the human approving an external post
should see the *actual content* being posted, not just a tool-name/
argument-hash abstraction. **Genuine gap**: no existing invariant requires
approval UI/UX to show human-readable content, only that approval occurs.
Not proposing a new invariant — this is an implementation-quality
requirement for whatever surfaces approval requests to Natalie, not a
governance question.

## Summary: invariant coverage

Of 16 threats reviewed, **12 map directly to an existing invariant**
(mostly I-09, several to I-05 and the Production Access Authorization
Gate). **4 are implementation-discipline concerns** (SSRF, command
injection, path traversal, approval-content visibility) with no
governance gap — standard secure coding applied to this specific
architecture. **1 genuine gap identified**: no existing invariant governs
independent review of a new tool's *declared* risk classification before
first registration (malicious/careless tool registration). One proposed
governance addition offered for that gap, explicitly not adopted.
