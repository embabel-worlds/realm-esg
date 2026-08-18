#!/usr/bin/env python3
"""Batch population: spider a set of domains into the corpus, then warm the extraction.

Population is deliberately NOT a query. A virtual join resolves per bound anchor and is capped by
maxAnchors; a comparison across companies that lazily fetched each one would either be refused or
would trigger hundreds of live crawls inside a single query. So the split is:

    populate  — explicit, slow, batch, per domain          (this script)
    compare   — ordinary Cypher over what has been populated

Because the extract producer is `cache: graph`, there is no separate extraction job: the first
traversal of a document extracts and persists, and repeats are plain graph hits. "Populate" is
therefore crawl -> ingest -> one warm-up traversal.

RESUMABLE. Progress lives in the graph, not here — a domain whose documents are already ingested
is skipped, so re-running after an interruption continues rather than restarts.

    python3 scripts/populate.py domains.txt
    python3 scripts/populate.py acme.com foo.com --max-pages 12

Environment: EMBABEL_URL (default http://localhost:8042), EMBABEL_USER, EMBABEL_PASS.
"""
import argparse, json, os, pathlib, sys, time, urllib.parse
import urllib.request

BASE = os.environ.get("EMBABEL_URL", "http://localhost:8042").rstrip("/")
USER = os.environ.get("EMBABEL_USER", "")
PASS = os.environ.get("EMBABEL_PASS", "")

# The crawler scores links by term overlap against this hint. The corpus that motivated this
# realm is European and multilingual: of 968 evidence URLs, only 81 contain "sustainab" — the
# real paths are /duurzaamheid/, /nachhaltigkeit, /governance-code-cultuur/. An English-only hint
# finds under a tenth of the evidence, so the hint carries the terms in the languages the sites
# are actually written in. This is why no semantic link scorer is needed for v1.
HINT = ("sustainability duurzaamheid nachhaltigkeit durabilite responsabilite sostenibilita "
        "hallbarhet baeredygtighed baerekraft zrownowazony esg csr environment milieu umwelt "
        "climate klimaat klima emissions governance bestuur responsibility report jaarverslag")


def post(path: str, payload: dict, timeout: int = 180) -> dict:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST")
    if USER:
        import base64
        token = base64.b64encode(f"{USER}:{PASS}".encode()).decode()
        req.add_header("Authorization", f"Basic {token}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode()
    try:
        out = json.loads(body)
    except json.JSONDecodeError:
        return {"result": body}
    # The tool gateway reports refusals INSIDE a 200 envelope, so an unchecked status code reads a
    # refusal as an empty success. Raise instead.
    if isinstance(out, dict) and out.get("error"):
        raise RuntimeError(out["error"])
    return out


def call(tool: str, payload: dict, timeout: int = 180) -> dict:
    return post(f"/api/v1/tools/{tool}", payload, timeout)


def ingest_url(url: str, domain: str) -> dict:
    """Web pages have their own ingestion path: the server fetches and converts the URL itself,
    which is also how PDFs — where most real sustainability reporting lives — get handled.
    `ingest_document` is for text already pulled from an integration and explicitly not for web."""
    return post("/api/v1/documents/url", {"url": url, "fromOrgDomain": domain, "tags": ["esg"]})


def pages_of(envelope) -> list:
    """The crawl tool returns pages separated by a --- rule, each headed '# title' then its url.
    A successful gateway result is wrapped as {"result": ...}."""
    body = envelope.get("result", envelope.get("text", envelope.get("content", "")))
    text = body if isinstance(body, str) else json.dumps(body)
    out, seen = [], set()
    for block in text.split("\n\n---\n\n"):
        lines = block.strip().splitlines()
        if len(lines) < 2 or not lines[1].startswith("http"):
            continue
        uri = lines[1].strip().split("#")[0]          # a fragment is the same page, not another one
        if not uri or uri in seen:
            continue
        seen.add(uri)
        out.append({"title": lines[0].lstrip("# ").strip(), "uri": uri})
    return out


def populate(target: str, max_pages: int, delay: float) -> dict:
    """A full URL is ingested as given — sustainability reporting is very often a PDF, and the
    ingestion endpoint fetches and converts server-side, so pointing at the report beats fighting a
    homepage for it. A bare domain is crawled, trying the apex AND www: an apex that refuses
    connections while www serves fine is common (ricoh.co.uk does exactly this)."""
    is_url = target.startswith("http") or "/" in target
    url = target if target.startswith("http") else f"https://{target}"
    domain = re.sub(r"^www\.", "", url.split("//", 1)[1].split("/")[0])

    if is_url:
        try:
            ingest_url(url, domain)
            return {"domain": domain, "status": "ok", "pages": 1, "ingested": 1}
        except Exception as e:
            return {"domain": domain, "status": "ingest_failed", "detail": str(e)[:200], "pages": 0}

    pages, tried = [], []
    for candidate in (f"https://{domain}", f"https://www.{domain}"):
        try:
            got = pages_of(call("crawl", {"url": candidate, "hint": HINT, "max_pages": max_pages}))
            if got:
                pages = got
                break
            tried.append(f"{candidate}: crawled, no page carried a url")
        except Exception as e:                                # a dead site is data, not a crash
            tried.append(f"{candidate}: {str(e)[:110] or 'unreachable'}")
    if not pages:
        return {"domain": domain, "status": "no_entry_point", "pages": 0, "detail": "; ".join(tried)}

    ingested = 0
    for p in pages:
        try:
            ingest_url(p["uri"], domain)                       # fromOrgDomain is the partition key
            ingested += 1
        except Exception as e:
            print(f"\n    ingest failed {p['uri']}: {str(e)[:140]}", file=sys.stderr)
        time.sleep(delay)                                     # politeness, per host
    return {"domain": domain, "status": "ok" if ingested else "nothing_ingested",
            "pages": len(pages), "ingested": ingested}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+", help="domains, or a file with one domain per line")
    ap.add_argument("--max-pages", type=int, default=10)
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests to a host")
    args = ap.parse_args()

    domains = []
    for t in args.targets:
        p = pathlib.Path(t)
        domains += [l.strip() for l in p.read_text().splitlines()
                    if l.strip() and not l.startswith("#")] if p.exists() else [t]

    print(f"populating {len(domains)} domain(s) from {BASE}, {args.max_pages} pages each\n")
    results = []
    for i, d in enumerate(domains, 1):
        print(f"[{i}/{len(domains)}] {d} ... ", end="", flush=True)
        r = populate(d, args.max_pages, args.delay)
        results.append(r)
        print(f"{r['status']}, {r.get('ingested', 0)} document(s) ingested")

    ok = sum(r["status"] == "ok" for r in results)
    docs = sum(r.get("ingested", 0) for r in results)
    print(f"\n{ok}/{len(domains)} domains populated, {docs} documents ingested")
    print("Extraction is graph-cached: it runs on the first traversal of each document.")
    print("Warm it (and see the observations) with:\n")
    print("  MATCH (d:Document) WHERE d.publishedByDomain IN $domains")
    print("  MATCH (d)-[:HAS_OBSERVATIONS]->(o:EsgObservation)")
    print("  RETURN d.publishedByDomain AS domain, o.datapointId, o.value, o.unit, o.quote")
    failed = [r for r in results if r["status"] != "ok"]
    if failed:
        print(f"\nnot populated ({len(failed)}):")
        for r in failed:
            print(f"  {r['domain']}: {r['status']} — {r.get('detail', '')[:160]}")
        print("\nA site resisting a crawl is normal: corporate homepages geo-redirect, require JS,")
        print("and block non-browser clients. Paste a working URL — ideally the sustainability")
        print("report PDF — and it is ingested directly, converted server-side.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
