# realm-esg

Sustainability disclosure intelligence: spider an organization's published material, chunk it
into a corpus, and extract **typed, cited observations** — a number where the standard asks for a
number, a narrative where it asks for a narrative, and an explicit `not_disclosed` where the
material is silent.

Observations are **framework-neutral**. One observed fact is captured once, cited once, and
projected into GHG Protocol, CSRD/ESRS, GRI, ISSB, SASB or IRIS+ language on demand.

```
Organization ─> Document ─[:HAS_OBSERVATIONS]─> EsgObservation ─[:DERIVED_FROM]─> Source (chunk)
                                                      │
                                                      └─> EsgDatapoint ─[:SATISFIES]─> EsgRequirement ─[:IN_FRAMEWORK]─> EsgFramework
```

Adding a framework is catalogue data — a file of requirements plus `SATISFIES` edges from
datapoints that already exist. It is never a re-extraction.

## Why

This realm was specified against a 5,011-row third-party ESG dataset covering 272 domains. That
dataset is the benchmark, and `docs/BASELINE_DEFECTS.md` regenerates the analysis from source:

- **67 of its 97 metrics have exactly one distinct answer: "Yes".** Absence is never recorded, so
  a company with no ESG policy is indistinguishable from one never assessed.
- **23 of the 27 metrics that ask for a number or a description are answered only "Yes"** — 216
  rows. *"What were your Scope 2 emissions (metric tons)?"* → `Yes`. *"Describe the past climate
  actions implemented"* → `Yes`, 79 times.
- **18.6% of rows carry no rationale**, and cited evidence includes `/cookie-policy`,
  `/terms-and-conditions/` and `/calendario/`.
- **Country of legal registration is TLD inference**: of 128 rows on a country ccTLD, 116 (91%)
  were assigned exactly the country the TLD implies.

The root cause is visible in its question text: these are self-report **survey** questions,
written to be sent to a company, then repurposed as prompts for scraping a website. Nothing holds
an answer to the form its own question demands.

| Their defect | What this realm does |
|---|---|
| Cannot say no | `not_disclosed` is a first-class value the extractor is told to prefer over a guess |
| "Yes" to a number | `answerType: quantity` — a number, a unit and a period, or nothing |
| Unsupported citations | every observation carries a verbatim quote **and** the chunk id, so a citation is checked, not asserted |
| Firmographics from the domain name | `sourceClass: registry` datapoints are never read from a website |

## Layout

| Path | What |
|---|---|
| `reference/frameworks.yml` | the seven frameworks this realm can speak |
| `reference/requirements-core.yml` | what each framework asks, in its own language |
| `reference/datapoints.yml` | **the atoms** — what we observe, and which requirements each answers |
| `reference/requirements-vendor-baseline.yml` | the benchmark questionnaire as a dialect, for a row-for-row diff (generated) |
| `types/esg.yml` | graph types, the `HAS_OBSERVATIONS` join, and text-to-Cypher examples |
| `producers/esg.yml` | the `kind: extract` producer and its prompt |
| `scripts/populate.py` | batch spider → corpus |
| `scripts/headtohead.py` | the scorecard |
| `views/esg.yml` | the read surface — coverage, profile, framework projection, silence, comparison |
| `apps/esg-populate.html` | **the big red button** — spider domains into the corpus |
| `apps/esg-scorecard.html` | what a company discloses, typed and cited, in any framework's language |
| `scripts/check-catalogue-sync.py` | **CI gate** — catalogue vs prompt vs enforced vocabulary |

## Populating

Nothing populates on its own. The realm ships no `cron/`, no `events/` and no scheduler — a realm
that silently spiders hundreds of company websites is not something that should wake up on its own.
The corpus grows only when someone asks. Two ways to ask:

**In the appliance** — open the **Populate** app, paste domains, press the button. It crawls each
site through the gateway for candidate URLs, then hands each URL to `POST /api/v1/documents/url`,
which fetches and converts server-side — so PDFs, where most real sustainability reporting lives,
are ingested too. Then open the **Scorecard** app: extraction is graph-cached and fires on the
first read.

**From a machine that can reach the appliance** — `scripts/populate.py` is a REST client, so it
needs network and credentials, not disk access:

```bash
EMBABEL_URL=https://<appliance> EMBABEL_USER=… EMBABEL_PASS=… \
  python3 scripts/populate.py domains.txt --max-pages 10
```

**Seeding is not optional and is not automatic.** Until it runs there are no `EsgDatapoint` nodes,
so the framework views return nothing even when the corpus is full. Seed once per user:

```bash
curl -XPOST "https://<appliance>/api/v1/admin/reference/seed?username=<you>"
```

## Views

| View | Answers |
|---|---|
| `EsgCoverage` | what has been assessed — **the denominator for everything else** |
| `EsgProfile` | one company's observations, with the quote each was read from |
| `EsgFrameworkReport` | the same observations in one framework's language |
| `EsgSilence` | `not_disclosed` (read it, found nothing) vs `not_assessed` (never looked) |
| `EsgDisclosureComparison` | disclosure rates by industry, **returning the cohort size as a column** |
| `EsgDatapointCatalogue` | what can be observed at all, and what each thing feeds |

## Running the head-to-head

```bash
python3 scripts/check-catalogue-sync.py                      # always, before anything
python3 scripts/build-vendor-baseline.py <export.tsv>        # regenerate the dialect + defects doc
python3 scripts/populate.py domains.txt --max-pages 10       # spider and ingest
python3 scripts/headtohead.py --domains domains.txt --export <export.tsv>
```

Extraction is graph-cached: there is no extraction job. The first traversal of a document
extracts and persists every datapoint the text supports; repeats are plain graph hits until the
document changes.

Population is deliberately not a query. A virtual join resolves per bound anchor and is capped by
`maxAnchors`, so a cross-company comparison that lazily fetched each company would either be
refused or would trigger hundreds of live crawls inside one query. Populate in batch; compare
over what has been populated — and **always report the cohort size**, because the set is whatever
has been assessed, never a market.

## State — 0.1.0

Honest about what is and is not done:

- **Every framework code is `verified: false`.** ESRS, GRI, ISSB and SASB codes here are
  provisional and have not been read off the published standards. The premise of this realm is
  that a citation can be checked; shipping unverified codes would be the defect we are attacking.
  Verify before showing any of this to anyone.
- **IRIS+ metric ids are placeholders** (`code: TBD`). They are a lookup task, not a guess.
- **13 datapoints, not 97.** A slice where several frameworks genuinely overlap — climate,
  energy, water, safety, diversity, governance. Only 11 of the benchmark's 97 metrics map onto
  them, so the diff is partial and says so.
- **Verified against a live appliance:** ingestion, the `PUBLISHED_BY` join, and every view's
  Cypher. A real run held 20 documents and 1,891 chunks across two domains.
- **Not yet verified:** extraction itself. No `EsgObservation` has ever been produced, so the
  typed-answer discipline — the entire premise — is still unproven.
- **No skill yet**, so population and querying are app- and script-driven rather than available
  from chat.
- **No versioning.** Observations are replaced when a document changes, not superseded. "Who
  added a policy this year" needs a curation lifecycle this realm does not yet have.
- **No staleness sweeper.** `staleAfter` is declared on every datapoint and nothing acts on it.
- **No `registry`-class datapoints yet** — country of registration and industry need a registry
  or Diffbot source, which is exactly why they are not scraped here.
