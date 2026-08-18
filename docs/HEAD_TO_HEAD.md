# Head to head

Three companies — SCHOTT, AXA, Ricoh UK — using **the baseline's own cited URLs** as input, so the
evidence is identical and every difference is analysis quality alone.

## v0.9.2

| | baseline | realm-esg |
|---|---|---|
| rows / datapoint answers | 107 | 42 |
| **distinct answer values across all rows** | 18 | 12 |
| quantitative questions answered with a number | **0.0%** | **100%** |
| answers that are an explicit negative | 0.9% | 66.7% |
| answers carrying verbatim evidence | 90.7% | 92.9% |
| evidence checkable offline (chunk retained) | no | **yes** |
| same number reported under two datapoints | n/a | 0 |

### The number that matters

**69 of the baseline's 107 rows — 64% — are the single word "Yes".** Another 18 are
"Very concerned" or "Concerned". Its 107 rows carry 18 distinct values between them; AXA's 31 rows
carry **four**.

Ours are 30 quantities, 6 booleans and 6 narratives, and a quantity resolves to a figure with a
unit or to `not_disclosed` — never to "Yes".

### Per company

| | baseline rows | their distinct answers | our datapoints | our disclosed |
|---|---|---|---|---|
| schott.com | 44 | 10 | 14 | 5 |
| axa.com | 31 | **4** | 14 | 5 |
| ricoh.co.uk | 32 | 12 | 14 | 4 |

### The same question, the same page

| company | their metric | baseline | realm-esg |
|---|---|---|---|
| schott.com | `ELE_USA_RED_MEA` | Yes | **100 percent** |
| schott.com | `PAS_CLI_ACT_IMP` | Yes | *"Our climate strategy follows a clear hierarchy…"* |
| axa.com | `ELE_USA_RED_MEA` | Yes | **100 percent** |
| axa.com | `CAR_RED_INI` | "Yes, a formal policy" | *"2030 reduction targets as a business…"* |
| ricoh.co.uk | `ELE_USA_RED_MEA` | "Measures … being implemented" | **50 percent** |
| ricoh.co.uk | `PAS_CLI_ACT_IMP` | Yes | *"Our carbon reduction plan, pre…"* |

### Where we say less than they do, and why that is the point

On SCHOTT, `CAR_RED_INI` and `GHG_MEA_YN` are "Yes" in the baseline and `not_disclosed` for us. Two
different reasons, both worth stating:

- The mapping is imperfect. `GHG_MEA_YN` asks *"were you implementing steps to reduce GHG
  emissions"* — a yes/no about effort, not a figure. It has no clean equivalent among our
  quantities, and forcing one would be the same category error the baseline makes throughout.
- Where it genuinely is a miss, it is a **visible** miss: the datapoint is listed as
  `not_disclosed` rather than absent, so the gap is in the output rather than hidden by it.

A dataset that answers "Yes" to everything is never wrong and never useful. Ours can be checked,
which means it can also be caught — see the Scope 1+2 case below.

## The combined Scope 1+2 defect — fixed, with a residue

Before: 641,081 tCO₂e was reported as **both** `ghg_scope1` and `ghg_scope2_location`, doubling the
total for anyone who added them.

Now: no value appears under two datapoints, `ghg_scope1` is `not_disclosed`, and the combined figure
has its own datapoint whose framework mapping is deliberately partial — it satisfies ESRS E1-6 and
ISSB S2, which ask for gross emissions and a total, but **not** GRI 305-1 or 305-2, which ask for
each scope separately. A GRI projection therefore shows the scopes as undisclosed, which is true.

The residue is the page itself:

> *"our direct and indirect emissions (Scope 1 and 2) amounted to around 1 million tonnes of CO₂e.
> The exact **(location-based)** footprint was 641,081 tonnes"*

The extractor still records 641,081 as `ghg_scope2_location`, citing the second sentence — which,
read alone, genuinely does describe a location-based footprint. `location-based` is a *method*, not
a scope, and rule 6 now says so with this exact sentence as its worked example, but the model still
prefers the local reading. The number is no longer double-counted; whether it belongs to Scope 2 or
to the combined figure remains arguable, and the quote lets a reader decide.

## The "accumulating observations" were two different bugs, neither of them accumulation

**The producer had no cache declaration.** Its header comment claimed graph caching from the first
commit — copied from `realm-legal`, which declares `cache: { kind: graph }`; the line itself never
was. So the producer was transient: every traversal re-ran the model at full cost and
`MATCH (o:EsgObservation)` in raw Neo4j returned **zero** however many observations a view had just
displayed. Declared now — first call 13.8s, repeats 0.1s, 14 rows persisted and stable.

**Long documents are extracted in windows, and every window answers every datapoint.** AXA's
280-chunk page makes five windows, so it holds 5 × 14 = 70 rows, most of them the `not_disclosed`
of a window that did not contain the relevant text. Returned raw, a well-disclosed company looks
mostly silent and every rate over rows is wrong — that alone was the 73.9% evidence figure, not any
regression in extraction. `EsgProfile` and `EsgExtract` now return one row per datapoint, preferring
a window that found something, and report `windowsDisclosing/windowsRead` so a `3/7` is visible.
AXA: 98 rows → 14.

## The AXA "anchoring bug" was a cost gate — fixed

Not anchoring at all. `VcCostGate` refuses a query whose **estimated cold model calls** exceed
`maxColdModelCalls`, and AXA's two pages (280 + 86 chunks, ~7 windows) crossed it together.
Bisected:

| case | result |
|---|---|
| ricoh.co.uk cold — 2 docs, 19 chunks | 14 rows |
| axa, either page alone, cold | 28 / 42 rows |
| axa, **both pages cold at once** | refused, 0 rows |
| axa, once cached | 14 rows |

Load-dependent, therefore intermittent: the same view worked or didn't depending on what happened
to be cached. And it failed as "the request was too broad" with no warning and no producer log
line — a company silently skipped while the run reported success.

`EsgExtract` now carries the documented opt-in `{ai: {materialize: true}}`. The gate is right for a
passive read and wrong for this view: reading documents is its whole purpose, and it is what the
Populate button calls, so the cost is exactly what was asked for. No other view carries it —
opening a scorecard must not be able to start an unbounded extraction run.

Verified on the case that failed: both AXA pages cold, 366 chunks, 14 rows, `SUCCEEDED`.
