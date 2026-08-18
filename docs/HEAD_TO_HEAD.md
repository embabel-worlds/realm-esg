# Head to head

Three companies, **the baseline's own cited URLs** as input, so the evidence is identical and any
difference is extraction quality alone.

## v0.8.1 — after the combined-scope fix, the graph cache, and per-window reduction

107 baseline rows against 42 datapoint answers (14 each for three companies).

| | baseline | realm-esg |
|---|---|---|
| quantitative/open questions answered with a figure | **0 of 14** | **6 of 6** |
| answers that are a negative / not-disclosed | 0.9% | 69.0% |
| answered rows carrying evidence | 90.7% | **92.3%** |
| same number reported under two datapoints | n/a | **0** |

## The difference, in their own rows

SCHOTT, asked about emissions:

| | |
|---|---|
| baseline | `PAS_CLI_ACT_IMP` → **"Yes"** |
| realm-esg | `ghg_scope3` → **1,300,000 tCO₂e**, quoting *"Upstream and downstream emissions (Scope 3) amounted to around 1.3 million tonnes of CO₂"* |

AXA, asked about climate action:

| | |
|---|---|
| baseline | `PAS_CLI_ACT_IMP` → **"Yes"** |
| realm-esg | `ghg_reduction_target` → *"2030 interim targets as an insurer: 20% reduction in the carbon intensity…"* |

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

## Open defect

- **`EsgExtract` anchoring is unreliable for AXA.** `WHERE d.uri CONTAINS $domain` materializes for
  schott.com and ricoh.co.uk but returned 0 for axa.com; an exact-URI anchor works. Not understood,
  and worth understanding — it is the difference between a company being read and silently skipped.
