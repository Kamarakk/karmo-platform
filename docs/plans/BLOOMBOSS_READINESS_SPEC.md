# BloomBoss Readiness Specification

Status: **DESIGN ONLY. BloomBoss is not implemented, not started.** Exists
so that KARMO Core (Foundation v1 + proposed Core v2) will not need
redesign later to support it — per this workstream's own goal. Produced
under the Core v2 Engineering Blueprint Program, Workstream 9.

## Entity model

| Entity | Represents | Key attributes (illustrative, not a schema) |
|---|---|---|
| `PLANT` | A botanical species/variety KARMO's inventory can reference | scientific name, common name(s) |
| `CULTIVAR` | A specific cultivated variety of a `PLANT` | parent `PLANT`, cultivar name, characteristics |
| `INVENTORY_ITEM` | One trackable unit of stock | `CULTIVAR` reference, quantity on hand, cost basis, location, unit type (mother plant / division / corm / rooted cutting / finished plant) |
| `PROPAGATION_BATCH` | A group of propagation units started together | source `INVENTORY_ITEM` (mother plant), method (corm/cutting/division/tissue culture), start date, expected yield, actual yield, loss count |
| `SUPPLIER` | An external source of stock or materials | name, contact, typical lead time |
| `IMPORT` | One inbound shipment from a `SUPPLIER` | supplier, items, landed cost components (item cost + shipping + duties/fees), arrival condition, loss-on-arrival count |
| `COST` | A cost-basis record attached to an `INVENTORY_ITEM` or `IMPORT` | amount, category (acquisition/shipping/duty/labor/loss-writedown) |
| `ORDER` | A customer purchase, across any `SALES_CHANNEL` | items, channel, price, fees, status |
| `CUSTOMER` | A buyer, potentially across multiple channels | contact info, channel identities (e.g. a Palmstreet handle, a website account) |
| `SHIPMENT` | Fulfillment of an `ORDER` | carrier, tracking, cost, status |
| `SALES_CHANNEL` | Where a sale happens | Palmstreet / website / social-platform-direct / wholesale / in-person |
| `CONTENT_ASSET` | A media asset (photo/video) usable across posts/listings | file reference, associated `INVENTORY_ITEM`/`CULTIVAR` |
| `SOCIAL_POST` | One external post referencing a `CONTENT_ASSET` | platform, content, scheduled/posted time, linked `CAMPAIGN` |
| `CAMPAIGN` | A grouped marketing effort | goal, associated `SOCIAL_POST`s, date range |

## Multiple sales channels

Palmstreet, website, and social platforms are each their own
`SALES_CHANNEL` value, not separate parallel schemas — every `ORDER`
references exactly one channel, and channel-specific fields (Palmstreet's
own fee structure, a website's own payment processor reference) live as
channel-scoped extension data on the order, not as channel-specific
tables duplicating the same core entity. This is the same lesson H0.2's
`document_id`/`document_version` design already teaches: one logical
entity, versioned/channeled attributes layered on top, not N parallel
copies of the whole model.

## Business quantities this domain must track correctly

- **Inventory quantities**: current count per `INVENTORY_ITEM`, decremented
  by `ORDER` fulfillment, incremented by `PROPAGATION_BATCH` yield or
  `IMPORT` receipt — never computed ad hoc, always a maintained running
  total with an audit trail of every adjustment (mirroring
  `document_registry`'s own "authoritative expected state, reconciled
  against actual" pattern, applied to physical stock instead of vectors).
- **Mother plants / corms / propagation**: `PROPAGATION_BATCH` explicitly
  separates *started* from *yielded* from *lost* — a mother plant is
  itself an `INVENTORY_ITEM` (a stock unit that produces future stock, not
  consumed by the act of propagating).
- **Cost basis and sale price → profit**: `COST` records accumulate onto
  an `INVENTORY_ITEM`'s cost basis; `ORDER`'s sale price minus that
  cost basis (plus shipping cost, minus any fees) is profit — computed at
  report time from durable records, never stored as a single mutable
  "profit" field that could drift from its inputs.
- **Shipping**: a `SHIPMENT`'s own cost is a distinct `COST` category from
  acquisition/landed cost — needed separately for both profit calculation
  and carrier performance analysis.
- **Loss/death**: an explicit, first-class outcome for both
  `PROPAGATION_BATCH` (expected vs. actual yield) and `IMPORT`
  (arrival condition) — never silently absorbed into "quantity is just
  lower than expected." A loss is a *recorded event* with a reason, not
  an unexplained gap, mirroring I-07's "no silent failure" principle
  applied to physical inventory instead of software failures.
- **Wholesale**: modeled as a `SALES_CHANNEL` value like any other, with
  its own pricing tier — not a structurally different entity.
- **Imports**: landed cost (item + shipping + duties/fees) must be
  captured at receipt time, before any `COST` allocation to individual
  `INVENTORY_ITEM`s, so per-unit cost basis is traceable back to one
  `IMPORT` record.

## READ / BUSINESS MUTATION / EXTERNAL COMMUNICATION — explicitly separated

Directly maps onto the Tool/Capability Registry's `capability_class` +
risk-flag design (Workstream 3, this program) — every BloomBoss tool a
future implementation registers falls cleanly into exactly one of these,
never a hybrid:

| Category | Example tools | `capability_class` | `financial_action` | `external_side_effects` |
|---|---|---|---|---|
| **READ** | read stock level, read order history, read profit report | `READ` | false | false |
| **BUSINESS MUTATION** | record a sale, record a loss, receive an import, adjust inventory | `REVERSIBLE_WRITE` | true (for anything touching revenue/cost) | false |
| **EXTERNAL COMMUNICATION** | post to social media, message a customer, respond to an incoming inquiry | `EXTERNAL_ACTION` | false (unless the message itself commits to a price/refund) | true |

Every **BUSINESS MUTATION** and **EXTERNAL COMMUNICATION** tool computes
to at least `EXPLICIT_PER_CALL` or `EXPLICIT_PER_SESSION_OR_TASK` approval
per the registry's own computation rule — exactly the standing
requirement `docs/vision/KARMO_PRODUCT_VISION.md` and
`docs/governance/KARMO_AUTONOMOUS_EXECUTION_CONTRACT.md` already establish
for real financial/customer-facing consequence.

## What this spec deliberately does not do

- No BloomBoss application code, schema, or table exists as a result of
  this document.
- No decision that BloomBoss *is* the first post-foundation capability —
  see `docs/plans/POST_FOUNDATION_CAPABILITY_ROADMAP.md`, unchanged by
  this spec.
- No integration with the real Palmstreet API, a real website backend, or
  any real social platform.

## Why KARMO Core won't need redesign for this

Every entity above is expressible as ordinary `REVERSIBLE_WRITE`/`READ`/
`EXTERNAL_ACTION` tools against the Tool/Capability Registry (Workstream
3) with its own domain-scoped schema/table namespace (per the
Extensibility Review's own recommendation, "give it its own schema/table
namespace from the start"), its own credential scope
(`failure_isolation`), and its multi-step workflows (import → cost
allocation → inventory → sale → shipment) expressible as Job/Event model
(Workstream 5) jobs where a step genuinely needs durable, resumable,
multi-stage execution rather than one atomic tool call.
