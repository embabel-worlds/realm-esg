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


# A figure the engine marks short is not the realm's figure, and a battery that counts it reports
# drift that is the source's. short(d) reads an answer's own error, reason, warnings and outcome and
# is None when the answer is whole, else the line that stands in for the figure: "REFUSED: <why>"
# or "PARTIAL <n>: <the engine's reason>". It reads both wires: a query answer (`rows`, `warnings`
# as strings opening with the engine's code) and a view envelope (`status`, `outcome`, `warnings`
# as {code, message}).
# Raw warning codes that mean rows or values may be missing (the engine's incompleteness kinds).
# Cost notes (FILTERED_IN_GRAPH, AGGREGATE_NOT_PUSHED, EMPTY_NOT_KEPT, PUSHDOWN_VALUE_UNMATCHED),
# FILTER_STARVED (an honest empty), STALE_COPY, FIELDS_WITHHELD and UNKNOWN_VIA leave every row in place.
SHORT_CODES = (
    "PARTIAL_RESULT", "PRODUCER_ERROR", "NEEDS_FILTER", "NEEDS_PRODUCER", "FILTER_REJECTED",
    "UNPUSHED_FILTER", "AMBIGUOUS_LABEL", "INCOMPLETE_TRAVERSAL", "INCOMPLETE_RANKING",
    "INCOMPLETE_AGGREGATE", "INCOMPLETE_INPUT", "MATERIALIZATION_FAILED", "REDUCTION_FAILED",
    "UNPARSEABLE_ANSWER", "TERMS_UNAVAILABLE", "COMPUTE_FAILED", "PROPERTY_NOT_STORED",
    "FOLLOW_CAPPED", "UNLINKED_CHILDREN", "RESOLUTION_DROPPED", "AGENTIC_DEGRADED",
    "SOURCE_UNANSWERED",
)
# The typed `reason` a query result carries when it is not a clean answer and not an honest empty.
SHORT_REASONS = ("UNBOUNDED", "PARTIAL_NOT_MATCHED", "UNPUSHED_FILTER", "DISCONNECTED",
                 "INTERNAL_ERROR", "WRITE_IN_PROGRESS", "KILLED", "TOO_EXPENSIVE")
# Public warning codes on a view envelope that mean the same.
SHORT_PUBLIC = ("PARTIAL", "REDUCTION_FAILED", "COMPUTE_FAILED", "PROPERTY_NOT_STORED",
                "AGENTIC_DEGRADED", "RATE_LIMITED", "SOURCE_UNAVAILABLE", "SOURCE_REJECTED",
                "INVALID_FILTER", "UNPUSHED_FILTER", "TOO_BROAD", "FETCH_CAPPED",
                "INDEX_UNAVAILABLE", "ARGUMENT_REFUSED")


def short(d, figure=None):
    tag = "PARTIAL" if figure is None else "PARTIAL %s" % (figure,)
    if not isinstance(d, dict):
        return "REFUSED: not an engine answer: " + str(d)[:160]
    if "outcome" in d or "status" in d:  # a view envelope
        err = d.get("error") or {}
        if d.get("status") != "SUCCEEDED":
            return "REFUSED: %s %s" % (d.get("status"), (err.get("code", "") + " " + err.get("message", "")).strip()[:160] if isinstance(err, dict) else str(err)[:160])
        ws = [w for w in d.get("warnings") or [] if isinstance(w, dict) and w.get("code") in SHORT_PUBLIC]
        if d.get("outcome") not in ("OK", "EMPTY") or ws:
            why = ws[0]["code"] + ": " + ws[0].get("message", "") if ws else "outcome " + str(d.get("outcome"))
            return "%s: %s" % (tag, why[:200])
        return None
    if d.get("error"):
        return "REFUSED: " + str(d["error"])[:160]
    if d.get("run"):
        return "%s: the run had not finished (%s)" % (tag, d["run"])
    ws = [w for w in d.get("warnings") or [] if isinstance(w, str) and w.split(":", 1)[0].strip() in SHORT_CODES]
    if ws:
        return "%s: %s" % (tag, ws[0][:200])
    if d.get("reason") in SHORT_REASONS:
        return "%s: reason %s" % (tag, d["reason"])
    return None


def post(path, body, timeout=600):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers=H, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def cypher(q, timeout=600):
    r = post("/api/v1/tools/kg_query", {"cypher": q}, timeout)
    if "error" in r:
        raise RuntimeError(r["error"][:200])
    # A short page of the source is how correct quotes get reported FABRICATED (the paging below
    # exists for the same reason), so it stops the audit rather than feed it.
    s = short(r.get("result") or {}, len((r.get("result") or {}).get("rows") or []))
    if s:
        raise Short(f"source read: {s}")
    return (r.get("result") or {}).get("rows") or []


class Short(RuntimeError):
    """An answer the engine marked short or refused: the audit cannot judge against it."""


def view_rows(name, args):
    """A view's rows, or Short: a partial extraction audits fewer answers and reads as fewer defects."""
    d = post(f"/api/v1/views/{name}/invoke", {"args": args})
    s = short(d, len(d.get("data") or []) if isinstance(d.get("data"), list) else 0)
    if s:
        raise Short(f"{name} {json.dumps(args)}: {s}")
    return d.get("data") or []


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
        for doc in view_rows("EsgDocuments", {"domain": dom}):
            print(f"  {dom}: reading {doc['uri'][:78]} ({doc['chunks']} chunks)…", flush=True)
            answers += view_rows("EsgExtractDocument", {"uri": doc["uri"]})
        if not answers:
            print(f"{dom}: no observations — populate first", file=sys.stderr)
            continue
        chunks = {r["id"]: r["text"] or "" for r in cypher(
            "MATCH (c:ContentElement) WHERE c.id IN " +
            json.dumps(sorted({a["chunkId"] for a in answers if a.get("chunkId")})) +
            " RETURN c.id AS id, c.text AS text")}
        # PAGE THE SOURCE. A single query came back with 366 of this domain's 396 chunks — the
        # read surface caps rows — so a quote living in one of the missing 30 was reported as
        # FABRICATED. An audit that invents defects is worse than no audit: it would have had us
        # "fix" correct extractions. Read in pages until a page comes back short.
        source, skip, PAGE = [], 0, 100
        while True:
            page = cypher(f"MATCH (c:ContentElement)-[:HAS_PARENT*]->(d:Document) "
                          f"WHERE d.uri CONTAINS '{dom}' RETURN c.text AS text "
                          f"SKIP {skip} LIMIT {PAGE}")
            source += [r["text"] or "" for r in page]
            if len(page) < PAGE:
                break
            skip += PAGE
        source = " ".join(source)

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
    try:
        sys.exit(main())
    except Short as e:
        print(f"AUDIT NOT RUN — {e}", file=sys.stderr)
        sys.exit(1)
