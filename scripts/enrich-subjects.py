#!/usr/bin/env python3
"""Resolve each assessed company's firmographics from Diffbot and store them as EsgSubject nodes.

Why a node of our own rather than realm-diffbot's bridge: that bridge hangs off the canonical
`Organization` spine, and those nodes are not reachable from the user here — measured, both
`MATCH (o:Organization {domain:…})` and the `HAS_DIFFBOT_ORG` hop return nothing while the
documents themselves are plainly visible. So the realm owns its subject node and joins on the
domain the corpus already uses.

What this buys: a ranking that means something. "SCHOTT discloses more than Espersen" says little
when one is a glass multinational and the other a 171-person fish processor.

This is CONTEXT, never a disclosure. Nothing written here is a fact the company published; it is
third-party data for reading what the company published, and `nbOrigins` is its confidence signal.

    python3 scripts/enrich-subjects.py            # every domain in the corpus
    python3 scripts/enrich-subjects.py acme.com   # or named ones

Environment: EMBABEL_URL, EMBABEL_USER, EMBABEL_PASS (and DIFFBOT_TOKEN on the server).
"""
import argparse, base64, datetime, json, os, sys, urllib.request

BASE = os.environ.get("EMBABEL_URL", "http://localhost:8042").rstrip("/")
H = {"Content-Type": "application/json",
     "Authorization": "Basic " + base64.b64encode(
         f"{os.environ.get('EMBABEL_USER','')}:{os.environ.get('EMBABEL_PASS','')}".encode()).decode()}


def post(path, body, timeout=180):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers=H, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def corpus_domains() -> list:
    rows = (post("/api/v1/views/EsgCoverage/invoke", {"args": {}}).get("data")) or []
    return sorted({r["domain"] for r in rows if r.get("domain")})


def enhance(domain: str) -> dict | None:
    r = post("/api/v1/tools/diffbot_enhance", {"type": "Organization", "url": domain})
    data = ((r.get("result") or r).get("data")) or []
    if not data:
        return None
    e = data[0].get("entity") or {}
    loc = e.get("location") or {}
    country = loc.get("country")
    return {
        "domain": domain,
        "name": e.get("name"),
        # Diffbot returns industries as plain strings here, not objects — checked against a live
        # response rather than assumed, because the same field is objects elsewhere in its API.
        "industries": [i if isinstance(i, str) else (i or {}).get("name") for i in (e.get("industries") or [])][:6],
        "nbEmployees": e.get("nbEmployees"),
        "country": (country or {}).get("name") if isinstance(country, dict) else country,
        "isPublic": e.get("isPublic"),
        "nbOrigins": e.get("nbOrigins"),
        "resolvedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("domains", nargs="*")
    args = ap.parse_args()
    domains = args.domains or corpus_domains()
    print(f"resolving {len(domains)} domain(s)\n")
    ok = 0
    for d in domains:
        try:
            sub = enhance(d)
        except Exception as e:
            print(f"  {d:22} lookup failed: {str(e)[:60]}", file=sys.stderr); continue
        if not sub or not sub.get("name"):
            print(f"  {d:22} not found in Diffbot")   # a real answer: not every company is in it
            continue
        try:
            post("/api/v1/tools/create_entry", {"type": "EsgSubject", "data": {k: v for k, v in sub.items() if v is not None}})
            ok += 1
            print(f"  {d:22} {str(sub['name'])[:26]:28}{str(sub.get('nbEmployees') or '?'):>7} staff  "
                  f"{str(sub.get('country') or '?'):14}{(sub['industries'] or ['—'])[0][:26]}")
        except Exception as e:
            print(f"  {d:22} write failed: {str(e)[:60]}", file=sys.stderr)
    print(f"\n{ok}/{len(domains)} resolved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
