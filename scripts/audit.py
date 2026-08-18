#!/usr/bin/env python3
"""Audit every extracted answer against the source text it claims to come from.

This is what makes an accuracy claim checkable rather than asserted, so it is deliberately built
to be UNPERSUADABLE: no model judges anything here. Quotes are verified by string containment
against the retained chunk text, and silence is probed with keyword search over the full document.
Cases the probe flags are printed for a HUMAN to read — the script never decides them.

    python3 scripts/audit.py schott.com axa.com ricoh.co.uk

Environment: EMBABEL_URL, EMBABEL_USER, EMBABEL_PASS.

Exit status is 1 when any CONFIRMED defect is found — a fabricated quote, a disclosed answer with
no quote, or a citation pointing at a chunk that does not contain it — so this can gate a release.
Recall candidates never fail the build: only a person can say whether a mention is a disclosure.
"""
import argparse, base64, json, os, re, sys, urllib.request

BASE = os.environ.get("EMBABEL_URL", "http://localhost:8042").rstrip("/")
AUTH = "Basic " + base64.b64encode(
    f"{os.environ.get('EMBABEL_USER','')}:{os.environ.get('EMBABEL_PASS','')}".encode()).decode()
H = {"Content-Type": "application/json", "Authorization": AUTH}
norm = lambda s: re.sub(r"\s+", " ", (s or "")).strip().lower()

# What a genuine disclosure of each datapoint would have to MENTION. Used only to decide which
# not_disclosed answers a person should look at; never to judge one.
PROBES = {
    "ghg_scope1": [r"scope\s*1"], "ghg_scope2_location": [r"scope\s*2"],
    "ghg_scope2_market": [r"market[- ]based"], "ghg_scope3": [r"scope\s*3"],
    "ghg_scope1_and_2": [r"scope 1 and 2"], "ghg_reduction_target": [r"\btarget", r"net[- ]zero"],
    "climate_transition_plan": [r"\bclimate\b"],
    "energy_consumption_total": [r"energy consumption", r"\bMWh\b", r"\bGWh\b"],
    "renewable_energy_share": [r"renewable"], "water_withdrawal_total": [r"\bwater\b"],
    "safety_incident_rate": [r"injur", r"accident", r"lost[- ]time", r"\bLTIF"],
    "board_gender_diversity": [r"\bwomen\b", r"\bgender\b", r"\bfemale\b"],
    "board_sustainability_oversight": [r"\bboard\b", r"committee"],
    "business_conduct_policy": [r"code of conduct", r"\bethic", r"anti[- ]corruption"],
}


def post(path, body, timeout=600):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers=H, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def cypher(q, timeout=600):
    r = post("/api/v1/tools/kg_query", {"cypher": q}, timeout)
    if "error" in r:
        raise RuntimeError(r["error"][:200])
    return (r.get("result") or {}).get("rows") or []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("domains", nargs="+")
    ap.add_argument("--json", help="write the full result here")
    args = ap.parse_args()

    confirmed, candidates, stats = [], [], {"disclosed": 0, "silent": 0}
    for dom in args.domains:
        # Per DOCUMENT, never per domain: one request per page keeps cost bounded and progress
        # visible, and avoids the case where a multi-page company stalls a single request.
        answers = []
        for doc in post("/api/v1/views/EsgDocuments/invoke", {"args": {"domain": dom}}).get("data") or []:
            print(f"  {dom}: reading {doc['uri'][:78]} ({doc['chunks']} chunks)…", flush=True)
            answers += post("/api/v1/views/EsgExtractDocument/invoke", {"args": {"uri": doc["uri"]}}).get("data") or []
        if not answers:
            print(f"{dom}: no observations — populate first", file=sys.stderr)
            continue
        chunks = {r["id"]: r["text"] or "" for r in cypher(
            "MATCH (c:ContentElement) WHERE c.id IN " +
            json.dumps(sorted({a["chunkId"] for a in answers if a.get("chunkId")})) +
            " RETURN c.id AS id, c.text AS text")}
        source = " ".join(r["text"] or "" for r in cypher(
            f"MATCH (c:ContentElement)-[:HAS_PARENT*]->(d:Document) WHERE d.uri CONTAINS '{dom}' "
            f"RETURN c.text AS text"))

        for a in answers:
            dp, val, quote = a["datapoint"], str(a.get("value")), a.get("quote") or ""
            if val == "not_disclosed":
                stats["silent"] += 1
                # Does the source mention the topic at all? If not, the silence corroborates itself.
                for pat in PROBES.get(dp, []):
                    m = re.search(pat, source, re.I)
                    if m:
                        candidates.append((dom, dp, pat, re.sub(r"\s+", " ", source[max(0, m.start()-90):m.end()+150])))
                        break
                continue

            stats["disclosed"] += 1
            if not quote.strip() or quote.strip() == "NONE":
                confirmed.append((dom, dp, "DISCLOSED WITH NO QUOTE — unsupported claim")); continue
            if norm(quote)[:100] in norm(chunks.get(a.get("chunkId"), "")):
                continue
            # The cited chunk does not contain it. Real text in the wrong place, or not there at all?
            confirmed.append((dom, dp, "QUOTE NOT IN SOURCE AT ALL — fabricated"
                              if norm(quote)[:90] not in norm(source)
                              else "quote is real but cited to the wrong chunk"))

    print(f"\nAUDIT — {stats['disclosed']} disclosed answers, {stats['silent']} silent\n")
    print(f"  CONFIRMED DEFECTS : {len(confirmed)}")
    for d, dp, why in confirmed:
        print(f"      {d:14}{dp[:32]:34}{why}")
    print(f"\n  recall candidates : {len(candidates)}  (topic mentioned; a PERSON must judge each)")
    for d, dp, pat, ctx in candidates:
        print(f"      {d:14}{dp[:32]:34}/{pat}/\n          …{ctx[:150]}…")
    if args.json:
        open(args.json, "w").write(json.dumps({"confirmed": confirmed, "candidates": candidates, "stats": stats}, indent=1))
    return 1 if confirmed else 0


if __name__ == "__main__":
    sys.exit(main())
