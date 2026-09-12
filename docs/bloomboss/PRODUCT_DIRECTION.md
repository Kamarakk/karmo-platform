# BloomBoss Product Direction

Status: APPROVED DIRECTION — IMPLEMENTATION DETAILS FLEXIBLE

## Product goal
BloomBoss is a shared, device-neutral business platform powered by KARMO. Natalie and Kamara use the same live business state from any supported device.

## Core principles
- One shared source of truth for inventory, purchases, propagation, listings, sales, customers, suppliers, analytics, and tasks.
- Separate user identities for Natalie and Kamara, with shared access to the same current business data.
- Every meaningful change should preserve who changed it, when, the source/device when known, and provenance/evidence.
- Device-neutral experience: iPhone, Samsung/Android, Fold, Mac, Windows, tablet, and future devices should reach the same system.
- Business logic stays server-side; phone-specific features are optional conveniences, not dependencies.
- Structured platform data is preferred over screenshots or scraping when an official/supported source exists.
- Screenshots/photos remain a practical fallback for supplier invoices and other data that has no cleaner structured source yet.
- Unknown historical values remain unknown; AI must not invent missing facts.

## Product layers
1. Business Data Layer — canonical business state.
2. Intelligence Layer — KARMO analysis, recommendations, pricing, forecasting, and decision support.
3. Workflow Layer — orders, shipping, listing, customer follow-up, tasks, and approved actions.
4. Experience Layer — responsive web/mobile UI plus voice, photo, video, text, file, and URL input.

## Data-source priority
1. Official APIs or supported structured integrations.
2. Official exports from marketplaces.
3. Shared files/documents.
4. Screenshot/photo evidence where needed.
5. Voice/text/manual correction for facts that do not exist elsewhere.

## Shared-user model
Natalie and Kamara are separate operators of the same BloomBoss system. Updates by either user become visible to the other through the same canonical state. Permissions may evolve later without changing the underlying shared-data model.

## Device strategy
Use a responsive, cross-platform interface as the primary experience. Apple Shortcuts, Android intents, Samsung features, Siri, Google Assistant, or other ecosystem-specific features may be added later as optional adapters.

## Universal Command & Capture
Voice, image, video, text, PDF, URL, and structured platform data feed one intake layer. The intake layer extracts or receives facts, validates them, preserves provenance, and routes proposed changes through KARMO authority boundaries before canonical updates.

## Marketing intelligence direction
Preserve source channel and, where available, discovery/attribution separately from transaction channel. Long-term analysis should support acquisition, conversion, revenue, margin, repeat purchase, retention, and customer lifetime value.

## Flexibility rule
This document locks the product direction, not the implementation stack. Frameworks, models, phone platforms, UI technology, integrations, and processing tools may change when a better system-fit option appears, without changing the product principles above.
