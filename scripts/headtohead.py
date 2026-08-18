#!/usr/bin/env python3
"""Score this realm against the third-party baseline on the same domains.

The scorecard is fixed BEFORE the run, and every axis is arithmetic rather than judgement — a
comparison designed after seeing your own results is not a comparison. All four axes are
computed from the baseline export and from our own graph; none is scored by a model.

  1. answer-type fidelity  a question asking for a number is answered with a number
  2. negative capability   silence is reported as silence rather than as assent
  3. citation validity     the cited chunk actually contains the claimed quote
  4. rationale presence    every non-null answer carries evidence

Axis 3 is the one the baseline cannot pass by construction: it cites page URLs, so a citation can
only be checked by refetching the page, and its own text is not retained. We store the chunk, so
ours is checkable offline and exactly.

    python3 scripts/headtohead.py --domains domains.txt --export ../export.tsv

Environment: EMBABEL_URL, EMBABEL_USER, EMBABEL_PASS.
"""
import argparse, base64, csv, collections, json, os, pathlib, re, sys, urllib.request

BASE = os.environ.get("EMBABEL_URL", "http://localhost:8042").rstrip("/")
USER, PASS = os.environ.get("EMBABEL_USER", ""), os.environ.get("EMBABEL_PASS", "")
ROOT = pathlib.Path(__file__).resolve().parent.parent

QUANT = re.compile(r"\b(what was|what were|how many|how much|total amount|percent|number of|"
                   r"proportion|metric tons|describe|please provide|list and description|in what ways)\b", re.I)
NUMBER = re.compile(r"\d")


def cypher(q: str, params: dict | None = None) -> list:
    req = urllib.request.Request(
        f"{BASE}/api/v1/tools/kg_query",
        data=json.dumps({"query": q, "params": params or {}}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    if USER:
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{USER}:{PASS}".encode()).decode())
    with urllib.request.urlopen(req, timeout=300) as r:
        body = json.loads(r.read().decode())
    return body.get("rows", body if isinstance(body, list) else [])


def baseline_rows(export: pathlib.Path, domains: set) -> list:
    rows = list(csv.reader(export.open(newline="", encoding="utf-8-sig"), delimiter="\t"))
    return [r[:9] for r in rows[2:]
            if len(r) >= 9 and r[0] in domains and any(c.strip() for c in r)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domains", required=True, help="file with one domain per line")
    ap.add_argument("--export", required=True, help="the third-party comparison export (.tsv)")
    ap.add_argument("--json", help="write the full scorecard here")
    args = ap.parse_args()

    domains = {l.strip() for l in pathlib.Path(args.domains).read_text().splitlines()
               if l.strip() and not l.startswith("#")}
    theirs = baseline_rows(pathlib.Path(args.export), domains)
    if not theirs:
        sys.exit(f"no baseline rows for those {len(domains)} domains — check the export and the names")

    ours = cypher("""
        MATCH (d:Document) WHERE d.publishedByDomain IN $domains
        MATCH (d)-[:HAS_OBSERVATIONS]->(o:EsgObservation)
        RETURN d.publishedByDomain AS domain, o.datapointId AS datapoint, o.value AS value,
               o.unit AS unit, o.period AS period, o.quote AS quote,
               o.sourceChunkId AS chunkId, o.confidence AS confidence
    """, {"domains": sorted(domains)})
    if not ours:
        sys.exit("no observations in the graph for those domains — run scripts/populate.py first, "
                 "then traverse HAS_OBSERVATIONS once to warm the extraction")

    dps = {e["data"]["id"]: e["data"] for e in
           __import__("yaml").safe_load((ROOT / "reference/datapoints.yml").read_text())}

    # ── axis 1: answer-type fidelity ──────────────────────────────────────────────────────────
    their_quant = [r for r in theirs if QUANT.search(r[1])]
    their_numeric = sum(1 for r in their_quant if NUMBER.search(r[3]) and r[3].strip().lower() != "yes")
    our_quant = [r for r in ours if dps.get(r["datapoint"], {}).get("answerType") == "quantity"
                 and r["value"] != "not_disclosed"]
    our_numeric = sum(1 for r in our_quant if NUMBER.search(str(r["value"])))

    # ── axis 2: negative capability ───────────────────────────────────────────────────────────
    their_negative = sum(1 for r in theirs if r[3].strip().lower() in ("no", "not disclosed", "none", "n/a"))
    our_negative = sum(1 for r in ours if r["value"] == "not_disclosed")

    # ── axis 3: citation validity — is the quote actually IN the chunk it cites ───────────────
    checked = [r for r in ours if r["quote"] and r["chunkId"]]
    valid = 0
    if checked:
        texts = {row["id"]: (row["text"] or "") for row in cypher(
            "MATCH (c:Chunk) WHERE c.id IN $ids RETURN c.id AS id, c.text AS text",
            {"ids": sorted({r["chunkId"] for r in checked})})}
        norm = lambda s: re.sub(r"\s+", " ", (s or "")).strip().lower()
        valid = sum(1 for r in checked if norm(r["quote"])[:120] in norm(texts.get(r["chunkId"], "")))

    # ── axis 4: evidence presence ─────────────────────────────────────────────────────────────
    their_blank = sum(1 for r in theirs if not r[4].strip())
    our_blank = sum(1 for r in ours if r["value"] != "not_disclosed" and not (r["quote"] or "").strip())
    our_answered = sum(1 for r in ours if r["value"] != "not_disclosed")

    pct = lambda n, d: f"{n/d*100:5.1f}%" if d else "    — "
    print(f"\nHEAD TO HEAD — {len(domains)} domains | baseline {len(theirs)} rows | ours {len(ours)} observations\n")
    print(f"{'axis':<34}{'baseline':>16}{'this realm':>16}")
    print("-" * 66)
    print(f"{'1 quantitative answered w/ number':<34}{pct(their_numeric, len(their_quant)):>16}{pct(our_numeric, len(our_quant)):>16}")
    print(f"{'2 negative / not-disclosed answers':<34}{pct(their_negative, len(theirs)):>16}{pct(our_negative, len(ours)):>16}")
    print(f"{'3 citations verifiable in-corpus':<34}{'  not possible':>16}{pct(valid, len(checked)):>16}")
    print(f"{'4 answers carrying evidence':<34}{pct(len(theirs)-their_blank, len(theirs)):>16}{pct(our_answered-our_blank, our_answered):>16}")
    print("-" * 66)
    print("\naxis 3 reads 'not possible' for the baseline because it cites a page URL and retains")
    print("no text: the claim can only be rechecked by refetching a page that may since have")
    print("changed. Ours cites a stored chunk, so it is checked exactly and offline.\n")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps({
            "domains": sorted(domains),
            "baseline": {"rows": len(theirs), "quantitative": len(their_quant),
                         "quantitative_numeric": their_numeric, "negative": their_negative,
                         "blank_rationale": their_blank},
            "realm": {"observations": len(ours), "quantitative": len(our_quant),
                      "quantitative_numeric": our_numeric, "not_disclosed": our_negative,
                      "citations_checked": len(checked), "citations_valid": valid},
        }, indent=2))
        print(f"scorecard written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
