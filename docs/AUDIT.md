# Precision and recall audit

Every one of the 42 answers this realm produced for SCHOTT, AXA and Ricoh UK, checked against the
stored source text. **No model graded its own work**: quote-in-source is string containment against
retained chunks, recall is a keyword probe over the full document, and every flagged case was read
by hand.

## Precision — 14 disclosed answers

| | |
|---|---|
| **quotes that are fabricated** | **0 of 13** |
| quotes attributed to the correct chunk | 11 of 13 |
| quote text real but cited to the wrong chunk | 2 of 13 |
| answers carrying no quote at all | **1 of 14** |

Two defects, both real, neither a hallucination:

- **AXA's transition plan and reduction target cite the wrong chunk id.** The quoted text exists —
  found in `c1f4ccd8…` and `58eedf95…`, not in the ids recorded. The claim is true and its
  provenance pointer is wrong, which matters precisely because the pointer is the product.
- **SCHOTT's climate transition plan has a value and no quote.** The prompt's rule 5 says no quote
  means no answer; the backend accepted it anyway. The rule is not enforced.

Value normalization is sound where checkable: *"around 1 million tonnes"* → `1000000` and
*"around 1.3 million tonnes"* → `1300000` are correct readings, not errors.

## Recall — 28 not-disclosed answers

The question that matters: is our silence honest, or are we blind? Probed every `not_disclosed`
against the full source text for topic-relevant terms.

| | |
|---|---|
| topic absent from the source entirely | 17 of 28 |
| topic present but correctly **not** a disclosure | 10 of 11 |
| **genuine misses** | **1 of 28** |

The ten correct ones are worth naming, because they are the cases a keyword-matching system gets
wrong: `board` matching SCHOTT's **"Job Board"** nav link; `women` matching AXA's **"Women in
Insurance"** menu item; `water` matching *"monitor carbon emissions, energy, water and paper
consumption"* with no figure; and — repeatedly — **a target mistaken for a measurement**, e.g. AXA's
*"60% reduction in Scope 1 and 2 emissions"*, which is a commitment, not an emissions figure. Each
was correctly left as `not_disclosed` and captured under `ghg_reduction_target` instead.

### The one miss

SCHOTT publishes, under "Science based targets":

> *"we have joined the Science Based Targets initiative (SBTi) and set ourselves ambitious CO₂
> reduction targets across all three emission scopes (Scope 1–3)"*

`ghg_reduction_target` returned `not_disclosed`. By this realm's own datapoint definition — *"a
stated ambition without a figure or date is still a target: quote it as published"* — that is a
miss. The rule is right and the extractor did not follow it.

## What this establishes, and what it does not

**Established:** the extractor does not invent evidence (0 of 13), its silence is overwhelmingly
honest (27 of 28), and it does not confuse a target with a measurement — the failure mode that
would make an ESG dataset actively misleading.

**Not established:** that every figure is *correct*. Numbers were checked against the sentence they
were drawn from, not against the company's actual reporting. `ghg_scope2_location = 641081` remains
arguable on an ambiguous page (see HEAD_TO_HEAD.md). Three companies, 42 answers, 14 datapoints —
not 272 companies and 97 metrics.

**Three fixes owed:** enforce rule 5 (no quote, no answer); correct the sourceIndex→chunk mapping;
make a target-shaped ambition without figures register as a target.
