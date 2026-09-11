# BloomBoss Build Plan

Status: **APPROVED PLANNING RECORD — NOT YET IMPLEMENTED**

This plan captures the BloomBoss architecture and phased build decisions made with Kamara on 2026-09-10. It extends `docs/plans/BLOOMBOSS_READINESS_SPEC.md`; it does not replace that readiness specification.

## Core product principle

BloomBoss should be built like a real human business team, not as a pile of disconnected automations.

For every major capability:

1. Model how a competent human would perform the job.
2. Identify the data the human would need.
3. Identify likely failure modes before automation.
4. Automate only the parts that add real value.
5. Keep visible health/status and a manual fallback.
6. Record what happened so later decisions can be evaluated against real outcomes.

The design should favor supported interfaces in this order:

1. official API
2. official integration
3. official export/import
4. authorized browser workflow only where necessary

Avoid brittle dependence on a marketplace UI when a supported integration path exists.

## Business architecture

The preferred long-term commerce architecture is:

`KARMO / BloomBoss master data -> Shopify -> Palmstreet / Facebook / Instagram / TikTok Shop`

and, where useful and supported:

`KARMO / BloomBoss master data -> Etsy API`

The BloomBoss/KARMO data layer remains the business source of truth. Shopify is an integration/commerce bridge, not the master business brain. Palmstreet and other marketplaces are sales channels.

A future direct Palmstreet integration can replace or supplement the Shopify bridge if Palmstreet exposes a stable supported API.

## Intelligence model

BloomBoss should ultimately develop nine connected intelligence areas.

### 1. Market Intelligence

Purpose: understand external demand, supply, competition, seasonality, pricing movement, and emerging plant trends.

Questions it should answer:

- What plants are becoming more or less desirable?
- Where is supply increasing?
- What price ranges are competitors asking?
- Which search or social signals are strengthening?

### 2. Product Intelligence

Purpose: determine what BloomBoss should buy, grow, propagate, retain, reduce, or stop carrying.

Important signals include sell-through, losses, propagation success, time to maturity, capital tied up, realized margin, and repeat demand.

### 3. Customer Intelligence

Purpose: understand who buys, what they buy, how often they return, average spend, channel preference, and customer value over time.

### 4. Pricing & Margin Intelligence

Purpose: recommend prices from BloomBoss economics rather than copying competitor asking prices.

Inputs should include landed cost, desired margin, market range, scarcity, maturity/quality, sales velocity, historical realized prices, channel fees, and observed price sensitivity.

### 5. Inventory & Supply Intelligence

Purpose: know what BloomBoss actually owns and what is becoming available.

Track physical stock, mother plants, propagations, imports, growing stock, reserved stock, listed stock, sold stock, losses, locations, and future expected availability.

### 6. Channel Intelligence

Purpose: determine where a specific product performs best.

Compare Palmstreet, Etsy, Shopify, TikTok, Meta, wholesale, and future channels by sell-through, margin, conversion, speed to sale, customer quality, and operational cost.

### 7. Live-Commerce Intelligence

Purpose: learn what makes BloomBoss live sales perform.

Possible measures include viewer arrival, engagement, product order, product pin timing, giveaway timing, sales per minute, conversion, products shown but not sold, and viewer drop-off.

### 8. Marketing & Content Intelligence

Purpose: determine which content and campaigns actually contribute to sales rather than simply generating engagement.

### 9. Operations & Reliability Intelligence

Purpose: make the business understandable when something breaks.

Major workflows should have health indicators, preflight checks, known failure modes, human-readable fault explanations, recovery steps, and manual fallback procedures.

## Decision Journal

BloomBoss should maintain a durable decision journal for meaningful business decisions.

Each entry should capture:

- what was known at the time
- what was predicted
- what was decided
- why the decision was made
- what actually happened

Example:

- bought/imported a cultivar because demand was rising
- predicted landed cost and expected sale range
- later record actual survival, sell-through, realized price, time to sale, and margin

The goal is for KARMO to learn from BloomBoss's own decisions and results rather than repeatedly relying on generic internet assumptions.

## Human-centered operations framework

BloomBoss should combine several existing operating ideas:

- **Service Blueprinting** for mapping customer-facing steps, operator actions, backstage systems, and dependencies.
- **FMEA** for identifying likely failure modes before automation.
- **Incident-management / SRE-style operations** for preflight, monitoring, recovery, and post-incident learning.
- **Retail merchandising disciplines** such as sell-through, ABC thinking, inventory turn, and days on hand.
- **CRM disciplines** such as cohort and RFM-style customer analysis.
- **Marketing attribution/funnel analysis** for understanding which channels and content lead to purchases.

The operating rule is:

`Model the human job -> identify failure points -> automate carefully -> monitor it -> provide manual fallback -> measure the business result.`

## Historical-data starting advantage

Kamara can provide approximately **7-9 months of purchase and sales history** and estimates that **90-98% of plants bought and sold can be reconstructed accurately**.

Therefore BloomBoss does **not** start from an empty data-collection phase.

The first implementation phase should ingest and normalize this historical business record so later intelligence has a strong baseline immediately.

Unknown historical values must remain explicitly unknown. The system must never silently invent costs, dates, fees, sale prices, or other financial facts.

## Phase 1 — Historical Data Intelligence

### Objective

Create the canonical historical BloomBoss dataset from the existing 7-9 months of purchase and sales history.

### Core records

- purchase/import batch
- supplier/vendor
- plant/cultivar
- inventory unit or quantity-level record
- cost components
- sale/order
- sales channel
- listing history
- plant status/loss event
- source/provenance record

### Key fields

Where known, capture:

- plant/cultivar
- vendor/supplier
- purchase/import date
- quantity acquired
- purchase cost
- shipping/import cost
- duties/fees where applicable
- landed cost
- unit or batch identity
- growing/ready/listed/sold/lost/retained/giveaway status
- listing channel
- actual sale channel
- actual sale price
- sale date
- known selling fees
- provenance/source of each historical value

### Initial analytics

- total revenue
- total landed cost
- gross profit
- gross margin
- sell-through rate
- loss rate
- average realized sale price
- average days to sale where dates are known
- performance by cultivar
- performance by supplier/vendor
- performance by sales channel
- capital tied up in unsold inventory

### Data rule

Raw historical imports and normalized canonical records must remain separable so original evidence is preserved.

## Phase 2 — Marketplace Research Workers

Build authorized research capabilities that gather legally accessible market information from BloomBoss selling channels and approved public sources.

Preferred sources include Palmstreet, Etsy, Shopify, Meta, TikTok, and other relevant channels where supported access exists.

The system should compare:

- BloomBoss realized prices
- competitor asking prices
- market supply
- search/demand signals
- channel-specific performance

Official APIs and integrations take precedence over scraping.

## Phase 3 — Pricing + Product Recommendations

Use BloomBoss historical economics plus marketplace research to recommend:

- whether to buy/import again
- how much to buy
- which plants to propagate more heavily
- which products are tying up capital
- target price range
- minimum acceptable price
- likely margin
- best sales channel

Recommendations must be explainable from source data.

## Phase 4 — Multi-Channel Commerce Hub

Goal: enter/maintain a product once and make it available across supported sales channels without duplicating business records.

Preferred path:

`BloomBoss/KARMO -> Shopify -> Palmstreet / Facebook / Instagram / TikTok Shop`

and separately where appropriate:

`BloomBoss/KARMO -> Etsy`

Critical requirement:

**One authoritative inventory record.**

If a one-of-one plant sells on one channel, the system must prevent a second sale elsewhere as quickly and reliably as supported integrations allow.

Channel-specific listing text, titles, pricing, and metadata can differ without duplicating the underlying plant/inventory identity.

## Phase 5 — Customer + Marketing Intelligence

Build analysis for:

- new vs returning customers
- purchase frequency
- average order value
- cultivar preference
- channel preference
- customer segments
- repeat-buyer behavior
- campaign/content contribution to sales
- reactivation opportunities

## Phase 6 — Operations & Reliability

Before automating live production, build the operational safety layer.

For every important workflow, define:

- health state
- preflight check
- failure mode
- customer/business impact
- immediate fallback
- troubleshooting location
- recovery procedure

A future BloomBoss operational health panel should use human-readable statuses such as:

- inventory sync
- Shopify sync
- marketplace connection
- network
- camera
- microphone
- OBS

Failures should explain what is wrong, what is affected, whether business can continue, and what action to take.

## Phase 7 — OBS / Live Production — intentionally last

OBS automation is deliberately last in the roadmap.

Reason: a live-selling workflow must remain usable even if KARMO, an overlay, or automation fails.

Rule:

**No OBS automation may be required for the live to continue.**

When eventually implemented, possible scenes include:

- Starting Soon
- Main Live
- Plant Spotlight
- Giveaway
- BRB
- Sold
- Thank You / End

KARMO may later update plant names, prices, photos, talking points, and scene data, but manual controls and fallback scenes must always remain available.

## Planned OBS use

OBS is useful as a professional production layer rather than as the commerce system itself.

Potential later flow:

`KARMO product/live data -> OBS overlays/scenes -> Palmstreet Seller Hub/live workflow -> supported multistream destinations`

OBS remote control must use authenticated interfaces and should be introduced only after the reliability layer exists.

## Relationship to existing KARMO components

### Core Control Layer (Core v2 prototypes)

Already built and tested. Planned for a later controlled production deployment after the current study session.

### Trusted Computer Worker System (Worker Runtime v0.1)

Already built and tested. Planned for controlled production deployment after the Core Control Layer, not before it.

### Experimental Hybrid Search (H0.3)

Do **not** deploy H0.3 as part of this plan.

Retain it as an experimental training/case-study asset for the AI/Agent Engineering Course, especially during the embeddings/RAG/retrieval section. It can later be re-evaluated with informed understanding rather than promoted automatically.

## Build order summary

1. Historical Data Intelligence
2. Marketplace Research Workers
3. Pricing + Product Recommendations
4. Multi-Channel Commerce Hub
5. Customer + Marketing Intelligence
6. Operations & Reliability
7. OBS / Live Production

## First implementation boundary

The first BloomBoss implementation should remain isolated on KARMO-DEV01.

Do not initially add:

- production deployment
- marketplace write automation
- OBS automation
- customer-facing external actions
- AI-generated financial facts

Before coding Phase 1, define and review:

1. directory structure
2. canonical data model
3. historical import format
4. acceptance criteria
5. invariant impact review

Then implement only the approved Phase 1 scope.

## Success criterion for the first release

The first release is successful when BloomBoss can ingest the historical business record and reproducibly answer meaningful questions such as:

- Which plants made the most money?
- Which purchases created the highest losses?
- Which suppliers produced the best realized return?
- Which cultivars took longest to sell?
- Which channels produced the strongest realized outcomes?
- Which inventory is still tying up capital?

The purpose of Phase 1 is to give every later BloomBoss capability a trustworthy business foundation rather than forcing KARMO to guess.
