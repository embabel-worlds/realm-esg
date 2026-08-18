# Head to head — first real run

Three companies, **the baseline's own cited URLs** as input, so the evidence is identical and any
difference is extraction quality alone. 107 baseline rows against 78 observations.

| | baseline | realm-esg |
|---|---|---|
| quantitative/open questions answered with a figure | **0.0%** (0 of 14) | **100%** (6 of 6) |
| answers that are a negative / not-disclosed | 0.9% | 78.2% |
| answered rows carrying evidence | 90.7% | 88.2% |

## The difference, in their own rows

SCHOTT's sustainability page, asked what its emissions are:

| | |
|---|---|
| baseline | `PAS_CLI_ACT_IMP` → **"Yes"** |
| realm-esg | `ghg_scope3` → **1,300,000 tCO₂e**, quoting *"Upstream and downstream emissions (Scope 3) amounted to around 1.3 million tonnes of CO₂"* |

AXA, asked about climate action:

| | |
|---|---|
| baseline | `PAS_CLI_ACT_IMP` → **"Yes"** |
| realm-esg | `ghg_reduction_target` → *"2030 interim targets as an insurer: 20% reduction in the carbon intensity…"* |

## The defect our own run has, and why it is visible

SCHOTT returned **641,081 tCO₂e for BOTH `ghg_scope1` and `ghg_scope2_location`** — wrong. The page
reports a combined figure, and the model split it across two datapoints instead of recording that it
could not separate them.

The quote is what exposes it: *"In the base year 2019, our direct and indirect emissions (Scope 1 and
2) amounted to around…"*. Anyone can see in one line that a combined number was double-counted.

That is the property being claimed here. Not that the extractor is never wrong — it is wrong in this
very run — but that a wrong answer arrives with the evidence that refutes it. A dataset whose cell
reads `Yes` with a link to `/cookie-policy` cannot be caught this way, by anyone, ever.

**Fix owed:** a combined-scope figure must record as `not_disclosed` for each scope separately, with
the combined value noted — or a `ghg_scope1_and_2` datapoint. Not yet done.

## Cost

| company | documents | model calls | observations |
|---|---|---|---|
| schott.com | 1 | 1 | 13 |
| ricoh.co.uk | 2 | 2 | 26 |
| axa.com | 1 | 3 | 39 |

One call per document (three where a page ran to 86 chunks), then graph-cached: repeats are free
until the document changes.
