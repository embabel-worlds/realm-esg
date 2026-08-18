# Ranking and scoring

Five views read PERSISTED observations and never trigger extraction, so they are cheap enough to
poll. They exist only because the producer declares `cache: { kind: graph }` — while observations
were transient, `EsgObservation` was a virtual label the engine refused to bind without an anchor,
so no query could sweep every company at once.

**Every view returns its cohort as a column.** A rate over this corpus is a rate over whatever has
been assessed; companies enter it because somebody asked about them, not because they were sampled.
A score without its n is not a score.

| View | Answers |
|---|---|
| `EsgLeaderboard` | who discloses most of the catalogue |
| `EsgDatapointRarity` | what almost nobody publishes |
| `EsgMetricRanking` | every company that published a figure, ranked, with its quote |
| `EsgConfidence` | quote coverage and window agreement — what a person should read first |
| `EsgTypeProfile` | figures vs narrative vs yes/no |

## Results — 9 companies, from the comparison set's own cited pages

### Disclosure completeness

| company | assessed | disclosing | % |
|---|---|---|---|
| schott.com | 14 | 6 | 43 |
| axa.com | 14 | 5 | 36 |
| ricoh.co.uk | 14 | 4 | 29 |
| ferrero.com | 14 | 3 | 21 |
| ucb.com | 14 | 3 | 21 |
| aet-tankers.com / cisco.com / hollandmalt.com | 14 | 2 | 14 |
| espersen.com | 14 | 1 | 7 |

This ranks **disclosure, not performance**. A company publishing a large emissions figure ranks
above one publishing nothing, which is the honest ordering when the source is the company's own
material.

### The finding that matters

**Six datapoints are disclosed by ZERO of nine companies:** Scope 1 emissions, market-based Scope 2,
total energy consumption, total water withdrawal, work-related injury rate, and board gender
diversity.

The quantitative core of ESG reporting is essentially **absent from corporate sustainability web
pages**. It lives in PDF reports and regulatory filings. That is a real limit on what any
website-based ESG dataset can deliver — including this one — and it is invisible in a dataset whose
columns all read "Yes", because a confirmation-only pipeline cannot tell you what it failed to find.

### What kind of disclosure

| company | figures | narrative | yes/no |
|---|---|---|---|
| schott.com | 4 | 2 | 0 |
| axa.com | 1 | 2 | 2 |
| ferrero.com | 1 | 2 | 0 |
| cisco.com | **0** | 2 | 0 |
| espersen.com | **0** | 0 | 1 |

Cisco's net-zero page is entirely narrative. The baseline scores it the same as SCHOTT, which
publishes tonnages — the distinction its questionnaire structurally cannot express.

### A ranking, with units and evidence

`renewable_energy_share`, after the pledge fix:

| company | figure | period | evidence |
|---|---|---|---|
| hollandmalt.com | 100% | | *"the world's first 100% emission-f…"* |
| schott.com | 100% | | *"Since the end of 2021, we have been covering our glo…"* |
| axa.com | 100% | since 2025 | *"Since 2025 AXA has been sourcing 100% of its electri…"* |
| ferrero.com | 94% | end of FY2024/25 | *"At the end of the fiscal year 2024/25, 24 of our pla…"* |

## The defect this view found on its first run

Ricoh ranked at **50%, period "by 2030"**, quoting *"We have committed to ensuring that at least 50%
of our…"* — a **pledge ranked as an achievement**, which makes a company that promised look like a
company that delivered. The most flattering error available, and therefore the one to be most
careful about.

Fixed: the renewable question now refuses future commitments, and prompt rule 9 generalizes it —
this was the third time a target had been read as a measurement. Verified by re-extraction: ricoh no
longer appears in the ranking at all, which is correct.

**Units are as published and are NOT converted.** A ranking across mixed units is wrong rather than
approximate; read `unit` before comparing.

---

# With firmographics joined (1.7.1)

`realm-diffbot` is installed on the appliance and `scripts/enrich-subjects.py` resolves every
assessed domain into an `EsgSubject` — industry, headcount, country, listed or not.

## Peer ranking

| company | industry | staff | country | disclosed | |
|---|---|---|---|---|---|
| espersen.com | Food & Drink | 171 | Denmark | 14/14 (100%) | |
| schott.com | Glassmaking | 17,392 | Germany | 6/14 (43%) | |
| ucb.com | Pharmaceutical | 9,765 | US* | 6/14 (43%) | |
| axa.com | Insurance | 107,756 | France | 5/14 (36%) | |
| ferrero.com | Food | 47,212 | Italy | 3/14 (21%) | |
| cisco.com | Security Software | 560 | US | 2/14 (14%) | **IDENTITY SUSPECT** |

## Size does not predict disclosure

| size band | companies | disclosed |
|---|---|---|
| under 250 | 3 | **43%** |
| over 5k | 4 | 36% |
| 250–5k | 1 | 14% |

The expected story — big companies disclose more — **does not hold here**. A 171-person Danish fish
processor discloses everything because it publishes a proper sustainability report, while several
multinationals publish marketing pages. Size predicts reporting FORMAT more than transparency. The
cohort is nine, so this is a hypothesis worth testing at scale, not a finding.

## The sector view is honest about being useless right now

Every industry has `companies: 1`. That is what the cohort column is for: a sector represented by
one company is an anecdote wearing a percentage. The view reports it rather than hiding it behind a
confident-looking rate, and it becomes useful at a few dozen companies per sector.

## The guard that earned itself immediately

Diffbot resolves `cisco.com` to **Sourcefire** — a company Cisco acquired — with 560 employees and
`nbOrigins: 170`. A confident wrong answer that the coverage signal does not catch, and one that
would have put Cisco in "Security Software" at 1/160th of its real headcount.

`domainNameMatch` catches it by asking whether the domain's own label survives in the resolved name.
It passes `hollandmalt` → "Holland Malt", `aet-tankers` → "AET", `espersen` → "A. Espersen", and
fails exactly the one that is wrong. `EsgPeerRanking` flags the row; `EsgSectorComparison` excludes
it, because a wrong industry moves two sector averages at once.

\* UCB is Belgian; Diffbot reports its PRIMARY LOCATION as the US. `country` is where Diffbot thinks
the company operates from, never country of legal registration — the distinction that made the
baseline's TLD-inferred registrations worthless.
