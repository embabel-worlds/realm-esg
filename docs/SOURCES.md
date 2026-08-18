# Which external sources are worth joining, and in what order

Measured before building, because both candidates turn out to depend on something we do not have.

## SEC EDGAR — not yet, and not for this reason you would expect

EDGAR is free, keyless and authoritative. It is also **almost irrelevant to this corpus**:

| | |
|---|---|
| spreadsheet domains | 272 |
| whose company name appears in EDGAR **at all** | 18 (7%) |
| our nine assessed companies | **1** (Cisco) |

The corpus is European and largely private — SCHOTT, Ferrero, Espersen, Holland Malt, AET are not
SEC registrants and never will be.

**The bigger problem is matching, not coverage.** EDGAR indexes by company NAME and CIK. It has no
domain index, so joining it to a corpus keyed on domain means fuzzy name matching, and fuzzy name
matching against 8,000 registrants produces confident nonsense:

| domain | EDGAR "match" |
|---|---|
| `imperial-tobacco.co.uk` | Canadian Imperial Bank of Commerce |
| `mitsui.com` | Sumitomo Mitsui Financial Group |
| `axa.com` | Axalta Coating Systems |
| `acacia-robinier.be` | Acacia Research Corp |
| `finance-in-motion.com` | Blue Owl Technology Finance Corp |

Five of the eighteen "matches" are different companies. Attributing a bank's filings to a tobacco
company is the same failure as ingesting the Schott Foundation's report for SCHOTT, and it is worse
here because a filing carries audited figures that look authoritative.

So EDGAR needs a **reliable domain → company identity bridge before it is safe at all**, which is
the thing it does not provide.

## Diffbot — the prerequisite, not a parallel option

Diffbot resolves a DOMAIN to a company identity, with industry, headcount, ownership chain and
tickers. That is exactly the bridge EDGAR lacks, and `realm-diffbot` already declares it as a
write-through join on `Organization.domain` — the key this realm already uses.

It also makes ranking mean something. "SCHOTT discloses more than Espersen" says little when one is
a glass multinational and the other a fish processor; "discloses more than its sector median at
similar headcount" is a comparison.

**Blocked on one credential.** The realm declares `token-env: DIFFBOT_TOKEN`. The appliance has no
Diffbot variable at all, and the only key in the estate is `DIFFBOT_API_KEY` in the dev repo's
`.env` — a different name. Installing it means setting `DIFFBOT_TOKEN` on the appliance container
and recreating it.

## What is already delivering more than either

`scripts/find-reports.py`. Espersen went from 1 of 14 datapoints to **14 of 14** once its own
sustainability report was read — the European equivalent of a filing is the CSRD statement and the
annual report, and both are PDFs on the company's own domain, reachable with the same-domain guard
already built. No credential, no identity bridge, no fuzzy matching.

## Order

1. **Report discovery, widened** — already works, no dependencies, biggest measured effect.
2. **Diffbot** — as soon as a token exists on the appliance. Unlocks sector-relative ranking and
   becomes the identity spine.
3. **EDGAR** — only after Diffbot, and only for the ~3% of this corpus it can honestly serve.
   Worth its own realm at that point; not worth putting in this one now.
