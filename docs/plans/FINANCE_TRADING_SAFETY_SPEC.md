# Finance / Trading Safety Specification

Status: **DESIGN ONLY. NO TRADING IMPLEMENTATION. No broker integration.**
Produced under the Core v2 Engineering Blueprint Program, Workstream 11.
Restates and operationalizes the standing constraint already established
in `docs/vision/KARMO_PRODUCT_VISION.md`: "any future trade-execution
capability requires an explicit human approval boundary... a
trade-execution action is, by definition, DESTRUCTIVE/HIGH-IMPACT under
I-09's classification." This document does not weaken that constraint —
it specifies exactly how the Tool/Capability Registry and Approval Engine
prototypes (Workstreams 3–4, this program) enforce it mechanically, not
merely by policy statement.

## Capability tiers, explicitly separated

| Tier | `capability_class` | `financial_action` | Example |
|---|---|---|---|
| `MARKET_DATA` | `READ` | false | read the latest quote for a symbol |
| `RESEARCH` | `READ` | false | pull fundamentals, news, historical data |
| `ANALYSIS` | `READ` or `DRAFT_PROPOSE` | false | compute an indicator, summarize a trend |
| `BACKTESTING` | `READ` | false | run a strategy against historical data, no live effect |
| `PAPER_TRADING` | `REVERSIBLE_WRITE` | false (no real money) | simulate an order against a synthetic ledger |
| `PORTFOLIO_ANALYSIS` | `READ` | false | read real holdings, compute real exposure/risk metrics |
| `TRADE_PROPOSAL` | `DRAFT_PROPOSE` | false | KARMO composes a specific, fully-parameterized proposed order and its reasoning — proposing is not executing |
| `TRADE_EXECUTION` | `DESTRUCTIVE_HIGH_IMPACT` | **true, hard floor** | actually place/modify/cancel a live order |

`TRADE_EXECUTION` is the one tier this entire specification exists to
constrain. Everything above it (`MARKET_DATA` through `TRADE_PROPOSAL`) is
ordinary `READ`/`DRAFT_PROPOSE` work KARMO may already do fairly
autonomously, matching the product vision's own "KARMO may analyze
autonomously" allowance.

## The required flow

```
KARMO analyzes autonomously (MARKET_DATA + RESEARCH + ANALYSIS + BACKTESTING + PORTFOLIO_ANALYSIS)
  -> proposes a trade (TRADE_PROPOSAL: exact, fully-parameterized, not vague)
    -> explains reasoning and risk (part of the same proposal, not a separate step Kamara must dig for)
      -> requests explicit approval (Approval Engine's request(), authority_class=DESTRUCTIVE_HIGH_IMPACT)
        -> approval binds to EXACT trade parameters (arguments_digest, per the Approval Engine's own design -- Workstream 4, this program)
          -> executes ONLY after a valid, matching, unexpired, single-use approval (Approval Engine's execute(), exactly as prototyped and tested tonight)
```

This is not a new mechanism invented for finance — it is the Approval
Engine prototype (Workstream 4) applied to its highest-stakes case. The
prototype's own test suite already proves the properties this domain
needs most:

- `test_changed_arguments_invalidates_the_approval` — a proposed trade
  approved at price $X cannot be silently executed at price $Y.
- `test_changed_tool_id_is_refused_approval_for_a_does_not_authorize_b` —
  an approval to buy cannot be reused to sell, or to trade a different
  symbol, or to place a different order type.
- `test_double_execution_is_refused_even_if_first_attempt_failed` — a
  failed order attempt cannot be silently retried against the same
  approval; a retry needs its own new proposal and its own new approval.
- `test_expired_approval_cannot_execute` — an approval granted against
  yesterday's market conditions cannot execute today.

## Never permit generic approval

**"Trade for me today" must never be an acceptable approval input.** The
Approval Engine's `arguments_digest` binding makes this structural, not
merely a UI convention: an approval record is bound to one specific
`tool_id` + `tool_version` + exact `arguments` dict at grant time; there
is no code path in the prototype (or the design it implements) that
accepts an approval scoped to "any trade" or "any order today." A generic
instruction like "trade for me today" cannot even be *represented* as a
valid approval request under this design — the `arguments` a request
declares must already be the exact, fully-parameterized order, per the
next section.

## Required exact-parameter fields for every `TRADE_EXECUTION` approval request

Every `finance.trading.place_order`-shaped (or `modify_order`/
`cancel_order`) tool's arguments must include, at minimum:

- **symbol** — the exact instrument, no wildcards.
- **side** — buy or sell, explicit.
- **quantity** — an exact number, never "some" or a percentage without
  the resulting exact quantity resolved before the approval is requested.
- **order type** — market, limit, stop, stop-limit, etc., explicit.
- **limit/stop price**, where the order type requires one.
- **account** — which specific account, when more than one exists.
- **expiration** — day order, GTC, or an exact expiry — never left
  implicit.
- **maximum loss**, where applicable (e.g. a stop-loss level, or an
  explicit max-loss cap the proposal itself commits to staying within).

A `TRADE_PROPOSAL` missing any of these is incomplete and must not be
escalated to an approval request — mirroring the Tool/Capability
Registry's own "refuse rather than guess" pattern (Workstream 3): an
incomplete proposal is refused, not filled in with an assumed default.

## Relationship to existing governance

This specification does not create new governance — it is the Finance
domain's own application of I-09 (capability classification, explicit
authorization for higher-impact capabilities) and the already-standing
constraint in `docs/vision/KARMO_PRODUCT_VISION.md`. No broker
credential, no live account, and no real order is touched by this
document or by any prototype in this program.

## What remains for a future, separately-scoped implementation

- Actual broker API integration (explicitly not tonight).
- The UI/surface through which Kamara actually reviews a `TRADE_PROPOSAL`
  and grants approval (the Approval Engine prototype proves the
  *backend* mechanism; presenting it clearly to a human is its own,
  separate design task — flagged also in Workstream 8's threat model,
  "social-media/account abuse" entry, for the analogous
  approval-content-visibility requirement).
- Real position/account-state integration for `PORTFOLIO_ANALYSIS` to
  read from (today: no such integration exists anywhere in KARMO).
