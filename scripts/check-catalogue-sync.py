#!/usr/bin/env python3
"""Fail the build when the catalogue and its three mirrors drift apart.

reference/datapoints.yml is the source of truth. Three places copy it and CANNOT read it at
runtime:

  1. producers/esg.yml       — the extraction prompt inlines every datapoint id and question,
                               because a prompt cannot read seeded reference data.
  2. types/esg.yml           — EsgObservation.datapointId carries an enforced `oneOf`; the
                               extract backend drops records whose id is off that list.
  3. reference/*.yml         — every SATISFIES target must be a requirement that exists.

A datapoint added to the catalogue but missing from the prompt is never extracted. A datapoint
in the prompt but missing from the `oneOf` is extracted and then silently dropped. Both fail
quietly, which is why this runs in CI rather than living in a comment.

    python3 scripts/check-catalogue-sync.py
"""
import sys, pathlib, yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
load = lambda p: yaml.safe_load((ROOT / p).read_text())
errs = []

datapoints = load("reference/datapoints.yml")
ids = [e["data"]["id"] for e in datapoints]
if len(ids) != len(set(ids)):
    errs.append(f"duplicate datapoint ids: {[i for i in ids if ids.count(i) > 1]}")

# 1 — every datapoint id and its question must appear in the extraction prompt
prompt = load("producers/esg.yml")[0]["extract"]["prompt"]
for e in datapoints:
    d = e["data"]
    if f"id: {d['id']}" not in prompt:
        errs.append(f"datapoint '{d['id']}' is in the catalogue but NOT in the extraction prompt — it will never be extracted")
    q = " ".join(d["question"].split())
    if q not in " ".join(prompt.split()):
        errs.append(f"datapoint '{d['id']}' question text differs between catalogue and prompt")

# 2 — the enforced oneOf must match the catalogue exactly
types = load("types/esg.yml")
obs = next(t for t in types if t["name"] == "EsgObservation")
allowed = obs["properties"]["datapointId"]["validation"][0]["values"]
if set(allowed) != set(ids):
    errs.append(f"types/esg.yml datapointId oneOf != catalogue. only-in-oneOf={set(allowed)-set(ids)} only-in-catalogue={set(ids)-set(allowed)}")

# 3 — no SATISFIES may dangle, and every framework referenced must exist
reqs = {e["data"]["id"]: e for e in load("reference/requirements-core.yml")}
frameworks = {e["data"]["id"] for e in load("reference/frameworks.yml")}
for e in datapoints:
    for rel in e.get("relations", []):
        if rel["to"]["id"] not in reqs:
            errs.append(f"datapoint '{e['data']['id']}' SATISFIES unknown requirement '{rel['to']['id']}'")
for rid, r in reqs.items():
    for rel in r.get("relations", []):
        if rel["to"]["id"] not in frameworks:
            errs.append(f"requirement '{rid}' IN_FRAMEWORK unknown framework '{rel['to']['id']}'")

# 4 — the shipped app catalogue must match reference/datapoints.yml
import json
app_cat = json.loads((ROOT / "apps/esg-catalogue.json").read_text())
app_ids = [d["id"] for d in app_cat["datapoints"]]
if set(app_ids) != set(ids):
    errs.append(f"apps/esg-catalogue.json != reference/datapoints.yml. "
                f"only-in-app={set(app_ids)-set(ids)} only-in-catalogue={set(ids)-set(app_ids)}")
for d in app_cat["datapoints"]:
    src = next((e["data"] for e in datapoints if e["data"]["id"] == d["id"]), None)
    if src and (d["name"] != src["name"] or d["answerType"] != src["answerType"]):
        errs.append(f"apps/esg-catalogue.json '{d['id']}' name/answerType differs from the catalogue")

# 5 — an unverified framework code must never be presented as authoritative
unverified = [rid for rid, r in reqs.items() if not r["data"].get("verified", False)]
orphans = [i for i in ids if not any(r["to"]["id"] in reqs for r in
                                     next(e for e in datapoints if e["data"]["id"] == i).get("relations", []))]
if orphans:
    errs.append(f"datapoints answering no framework requirement: {orphans}")

if errs:
    print("CATALOGUE OUT OF SYNC\n" + "\n".join(f"  - {e}" for e in errs), file=sys.stderr)
    sys.exit(1)

print(f"catalogue in sync: {len(ids)} datapoints, {len(reqs)} requirements, "
      f"{len(frameworks)} frameworks, {sum(len(e.get('relations', [])) for e in datapoints)} mappings")
print(f"NOTE: {len(unverified)}/{len(reqs)} requirement codes are still `verified: false` — "
      f"they must be checked against the published standards before being shown to anyone.")
