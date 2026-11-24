"""Offline preparation and descriptive scoring for the independent S1/S2 studies."""

import argparse
import csv
import hashlib
import json
import random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from calamityos.domain import _decision, milestones_for


SYSTEMS = ("B0", "B1", "P")
DATE_TASKS = (
    ("committee", 15, "committee meeting", "2026-12-27"),
    ("request", 45, "borrower-requested invocation", "2027-01-31"),
    ("extended", 75, "borrower-requested invocation with the one-time extension granted", "2028-02-29"),
    ("implementation", 135, "implementation on the bank-initiated route", "2026-10-01"),
    ("optout", 135, "end of borrower opt-out, including after booking", "2026-08-31"),
)
CASE_TASKS = (
    "boundary", "second_loan", "missing_snapshot", "nonstandard", "date_choice",
    "area_edge", "area_unknown", "refinance", "purpose", "evidence", "prior_relief",
)


def cases():
    for k, (template, offset, target, anchor) in enumerate(DATE_TASKS):
        for v in range(5):
            reference = date.fromisoformat(anchor) + timedelta(days=v)
            convention = "include_first" if (k+v) % 2 else "exclude_first"
            settings = {"declaration": reference.isoformat(), "day_count": convention, "route_task": template}
            yield {"id": f"{template}-{v+1}", "template": template, "type": "date",
                   "input": settings, "question": f"Declaration {reference}. Find the date for {target}. "
                   f"Approved counting convention: {convention}. Return an ISO date."}
    for template in CASE_TASKS:
        for v in range(5):
            # Everything needed to decide is visible to the annotators and baselines.
            snapshots = [{"dpd": 0, "classification": "Standard"},
                         {"dpd": (28+v if template in ("boundary", "second_loan") else 0),
                          "classification": "Substandard" if template == "nonstandard" else "Standard"}]
            if template == "boundary":
                snapshots = snapshots[1:]
            if template == "missing_snapshot" and v != 3:
                snapshots[1] = None
            if template == "nonstandard" and v in (1, 4):
                snapshots[1]["classification"] = "Standard"
            reading = "reference" if template == "date_choice" else "occurrence"
            area = ({"area_edge": "Outside declared area", "area_unknown": "Unresolved location"}.get(template, "Kalyandurg")
                    if v != 2 else "Kalyandurg")
            row = {"facilities": [], "old_relief": template == "prior_relief" and v != 3,
                   "covered_purpose": template != "purpose" or v == 2, "refinance": template == "refinance" and v != 4,
                   "loss_matched": template != "evidence" or v == 1, "guarantor": False}
            if v == 4 and template not in ("missing_snapshot","date_choice","boundary","second_loan"):
                snapshots[0]["dpd"] = 34
            for j, snap in enumerate(snapshots):
                history = {"occurrence": snap, "reference": {"dpd": 29+v, "classification": "Standard"}}
                row["facilities"].append({"id": f"study-{template}-{v+1}-{j+1}", "product": "Term loan",
                                         "mandal": area, "snapshots": {k: s for k,s in history.items() if s is not None}})
            yield {"id": f"{template}-{v+1}", "template": template, "type": "eligibility",
                   "input": {"row": row, "reading": reading}, "question":
                   f"Use the {reading} snapshot. Kalyandurg is in scope. Loss-list evidence is required. "
                   "Classify the borrower as Eligible, Ineligible, or Review under the scenario rules."}


def _write_csv(path, fields, rows):
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def prepare(directory):
    directory.mkdir(parents=True, exist_ok=False)
    items = list(cases())
    (directory/"vignettes.json").write_text(json.dumps(items, indent=2), encoding="utf-8")
    for template in ("annotator1", "annotator2", "reconciled"):
        _write_csv(directory/f"{template}.csv", ["id", "answer"],
                   ({"id": item["id"], "answer": ""} for item in items))
    _write_csv(directory/"held_out.csv", ["state","source_type","source","criterion","expressible",
               "field_status","minutes","notes"], [{"state":"Telangana"}, {"state":"Assam"}])


def _csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _answers(directory, name, ids):
    rows = _csv(directory/f"{name}.csv")
    if len(rows) != len(ids) or {r["id"] for r in rows} != ids or any(not r["answer"].strip() for r in rows):
        raise ValueError(f"{name}.csv requires one completed answer per vignette")
    return {r["id"]: r["answer"].strip() for r in rows}


def freeze(directory):
    items = json.loads((directory/"vignettes.json").read_text(encoding="utf-8"))
    ids = {item["id"] for item in items}
    for name in ("annotator1", "annotator2", "reconciled"):
        _answers(directory, name, ids)
    with (directory/"frozen.json").open("x", encoding="utf-8") as handle:
        json.dump({f: _hash(directory/f) for f in ("vignettes.json","annotator1.csv","annotator2.csv","reconciled.csv")},handle,indent=2)


def frozen_items(directory):
    checks = json.loads((directory/"frozen.json").read_text(encoding="utf-8"))
    if set(checks) != {"vignettes.json","annotator1.csv","annotator2.csv","reconciled.csv"}:
        raise ValueError("Incomplete study manifest")
    if any(_hash(directory/f) != digest for f,digest in checks.items()):
        raise ValueError("Frozen materials changed")
    return json.loads((directory/"vignettes.json").read_text(encoding="utf-8"))


def pipeline(directory):
    items = frozen_items(directory)
    def predict(case):
        data = case["input"]
        if case["type"] == "date":
            steps = milestones_for(date.fromisoformat(data["declaration"]), data["day_count"])
            index = {"committee":0, "request":1, "extended":2, "implementation":3, "optout":3}
            return steps[index[data["route_task"]]]["date"]
        return _decision(data["row"], data["reading"])[0]
    _write_csv(directory/"P.csv", ["id","run","answer"],
               ({"id":item["id"],"run":run,"answer":predict(item)} for run in range(1,6) for item in items))


def _score_runs(path, gold, groups):
    submitted = _csv(path)
    answers = {(r["id"], int(r["run"])):r["answer"].strip() for r in submitted}
    keys = {(k, run) for k in gold for run in range(1,6)}
    if len(submitted) != len(keys) or set(answers) != keys or not all(answers.values()):
        raise ValueError(f"{path.name} requires one explicit answer or ABSTAIN per case per run")
    abstentions = sum(a == "ABSTAIN" for a in answers.values())
    scores = {k: sum(answers[k,r] == a for r in range(1,6)) for k,a in gold.items()}
    clustered = defaultdict(list)
    for k,s in scores.items():
        clustered[groups[k]].append(s)
    clusters = list(clustered.values())
    rng = random.Random(20261120)
    rates = []
    for _ in range(2000):
        values = [n for group in rng.choices(clusters, k=len(clusters)) for n in group]
        rates.append(sum(values)/(len(values)*5))
    rates.sort()
    return {"correct":sum(scores.values()), "total":len(answers),
            "answered_excluding_abstentions":len(answers)-abstentions,"abstentions":abstentions,
            "items_right_all_five":sum(n==5 for n in scores.values()), "items":len(gold),
            "accuracy_95pct_template_cluster_bootstrap":[rates[49],rates[1949]],
            "misses_or_abstentions":[{"id":k,"correct_runs":v} for k,v in scores.items() if v<5]}


def score(directory):
    groups = {case["id"]:case["template"] for case in frozen_items(directory)}
    ids = set(groups)
    gold = _answers(directory, "reconciled", ids)
    first, second = [_answers(directory, f"annotator{i}", ids) for i in (1,2)]
    result = {"independent_agreement": sum(first[k] == second[k] for k in ids), "items":len(ids),
              "systems":{}}
    for system in SYSTEMS:
        if (directory/f"{system}.csv").is_file():
            result["systems"][system] = _score_runs(directory/f"{system}.csv", gold, groups)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("prepare","freeze","pipeline","score"))
    parser.add_argument("directory",type=Path)
    args = parser.parse_args()
    try:
        if args.action == "score":
            print(json.dumps(score(args.directory), indent=2))
        else:
            {"prepare":prepare,"freeze":freeze,"pipeline":pipeline}[args.action](args.directory)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
