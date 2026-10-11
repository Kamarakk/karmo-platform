# BloomBoss real historical data

This directory holds real, ingested historical purchase/sale records in the
`docs/bloomboss/HISTORICAL_IMPORT_TEMPLATE.csv` format — distinct from that
file, which stays a synthetic example only.

Per the build plan's data rule, raw historical imports and normalized
canonical records remain separable so original evidence is preserved. Per
KARMO's standing no-PII-in-source-control constraint, only business
purchase/sale facts are recorded here — never customer contact
information, home addresses, phone numbers, or other personal data. Source
documents that contain such information (e.g. a supplier invoice image)
are extracted into a clean CSV and never committed themselves.

## `emgarden_invoice_2026040040.csv`

Source: EMgarden (Xiamen, China) invoice #2026040040, dated 2026-04-21,
75 units across 13 cultivars, $4,711.80 in item cost + $705.00 freight to
Miami = $5,416.80 total (verified: this file's `allocated_landed_cost`
column sums back to exactly $5,416.80 across all 75 units, confirmed via
`python3 -m bloomboss.report`).

Freight was one shipment-level charge across all 13 cultivars, not a
per-batch cost — prorated evenly at $705.00 / 75 = $9.40/unit into each
unit's `allocated_landed_cost`, rather than recorded in
`batch_shipping_total`, to avoid double-counting. This is a disclosed
modeling assumption, not an invented financial fact.

5 of the 75 units (one each of Pink Black Velvet, Ninja Albo, Melo Aurea,
Stingray Aurea, Gloriosum Tricolor) are marked `sold` with real sale
prices Kamara provided, cross-matched to this invoice by cultivar name and
exact unit cost. The remaining 70 units are marked `growing` — their
actual outcome (sold/lost/retained) is genuinely unknown as of this
import, not assumed.

## `thailand_order_0023.csv`

Source: order summary ORD-0023 from Thai supplier Arisa, dated 2026-09-10,
shipping batch "USA-Sep 20", ship date 2026-09-14. 12 units across 10 order
lines, $3,039.00 in item cost, $0 shipping on the order (cargo and UPS are
billed separately per shipment and were not given for this order). Payment
status on the summary: unpaid, $3,039.00 remaining (฿98,768 at 32.50 THB/USD).
The buyer name on the summary is personal data and is not recorded.

One Longiloba Lava is a free replacement and is recorded as its own batch at
$0 cost. Each unit's `allocated_landed_cost` is its item price only, because
the freight for this order is unknown. All 12 units are marked `growing`;
their outcome is unknown as of this import. Cultivar spellings were
normalized ("Reginea" to "Reginae", title case).

Not in the CSV (no line items): Arisa's 2026-08-30 shipment, 5 boxes; box
WBOX#2, 60 x 32 x 26, cargo $228.00 plus UPS options (2nd Day Air $100,
Next Day Air Saver $149, Next Day Air Early $187). Kamara asked Arisa to keep
a remaining balance as credit toward the next order; the credit amount was
not stated.
