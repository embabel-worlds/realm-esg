#!/usr/bin/env python3
"""Find and ingest an organization's own sustainability REPORTS — the PDFs, not just its web pages.

Why this exists: measured across nine companies, SIX datapoints were disclosed by ZERO of them —
Scope 1, market-based Scope 2, total energy, water withdrawal, injury rate, board gender diversity.
The quantitative core of ESG reporting is not on sustainability web pages. It is in the annual
report and the CSRD sustainability statement, which are PDFs.

    python3 scripts/find-reports.py schott.com ucb.com --ingest

THE SAME-DOMAIN GUARD IS NOT OPTIONAL. An unrestricted "company sustainability report pdf" search
returns other companies' reports — a search for SCHOTT's returned the Schott FOUNDATION's (a
different organization), Franke's, Stada's and Schneider's. Attributing another company's emissions
is far worse than a gap: a gap is visible and a wrong attribution is not. So every query is
site-restricted AND every result's host is re-checked before it is ingested, because a search engine
honours `site:` as a hint rather than a contract.

Environment: EMBABEL_URL, EMBABEL_USER, EMBABEL_PASS.
"""
import argparse, base64, json, os, re, sys, urllib.parse, urllib.request

BASE = os.environ.get("EMBABEL_URL", "http://localhost:8042").rstrip("/")
H = {"Content-Type": "application/json",
     "Authorization": "Basic " + base64.b64encode(
         f"{os.environ.get('EMBABEL_USER','')}:{os.environ.get('EMBABEL_PASS','')}".encode()).decode()}

# Ordered by how likely each is to reach a document with FIGURES in it rather than prose.
QUERIES = [
    "site:{d} sustainability report pdf",
    "site:{d} CSRD sustainability statement pdf",
    "site:{d} annual report greenhouse gas emissions pdf",
    "site:{d} ESG data scope 1 scope 2 pdf",
]

# A report, not a product sheet or a press release.
WANTED = re.compile(r"(sustainab|csrd|esg|annual[-_ ]?report|non[-_ ]?financial|climate|emission|impact)", re.I)
UNWANTED = re.compile(r"(press[-_ ]?release|datasheet|product|brochure|catalog|price|terms|privacy|cookie)", re.I)


def post(path, body, timeout=300):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers=H, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def search(q, count=8):
    r = post("/api/v1/tools/brave_webSearch", {"q": q, "count": count}, 120)
    res = r.get("result") or r
    if isinstance(res, str):
        return []
    return (res.get("web") or {}).get("results") or res.get("results") or []


def on_domain(url: str, domain: str) -> bool:
    """The host must BE the domain or a subdomain of it. `reports.ucb.com` counts; `ucb.com.cn` and
    `schottfoundation.org` do not — the second is exactly the trap, being a different organization
    whose name contains the company's."""
    host = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    return host == domain or host.endswith("." + domain)


def candidates(domain: str) -> list:
    seen, out = set(), []
    for template in QUERIES:
        for hit in search(template.format(d=domain)):
            url = (hit.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            if not on_domain(url, domain):          # the guard, applied to the RESULT not the query
                continue
            title = hit.get("title") or ""
            if UNWANTED.search(url) or UNWANTED.search(title):
                continue
            is_pdf = ".pdf" in url.lower()
            if not (is_pdf or WANTED.search(url) or WANTED.search(title)):
                continue
            out.append({"url": url, "title": title.strip(), "pdf": is_pdf})
    # PDFs first: a report carries the figures a landing page describes.
    return sorted(out, key=lambda c: (not c["pdf"],))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("domains", nargs="+")
    ap.add_argument("--ingest", action="store_true", help="ingest what is found (otherwise list only)")
    ap.add_argument("--max-per-domain", type=int, default=3)
    args = ap.parse_args()

    for domain in args.domains:
        found = candidates(domain)[: args.max_per_domain]
        print(f"\n{domain} — {len(found)} candidate(s)")
        for c in found:
            kind = "PDF" if c["pdf"] else "page"
            print(f"  {kind:4} {c['title'][:52]:54}{c['url'][:80]}")
            if not args.ingest:
                continue
            try:
                r = post("/api/v1/documents/url",
                         {"url": c["url"], "fromOrgDomain": domain,
                          "tags": ["esg", f"domain:{domain}", "report" if c["pdf"] else "page"]})
                print(f"       -> {r.get('status')} {str(r.get('title') or r.get('message'))[:60]}")
            except Exception as e:
                print(f"       -> failed: {str(e)[:70]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
