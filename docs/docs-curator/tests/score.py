#!/usr/bin/env python3
"""Score a docs-curator output folder against the answer key.

    python score.py --out OUT --expected corpus_expected.yaml [--with-llm]

Prints ALL EXPECTATIONS MET and exits 0 on a match, else lists mismatches
and exits 1. --with-llm adds the checks that only a real LLM phase can fail:
every cluster has a verdict, and every conflict quote appears verbatim.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORK = ".docs-curator"


def score(out, expected, with_llm=False):
    work = Path(out) / WORK
    bad = []
    rows = {}
    for line in (work / "decisions.jsonl").read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        rows[d["path"]] = d
    for path, want in expected["files"].items():
        got = rows.get(path)
        if got is None:
            bad.append(f"{path}: no decision")
            continue
        for key in ("action", "reason", "kept_instead"):
            if key in want and got[key] != want[key]:
                bad.append(f"{path}: {key} is {got[key]!r}, expected {want[key]!r}")
    for path in sorted(set(rows) - set(expected["files"])):
        bad.append(f"{path}: not in the answer key")

    conflicts = json.loads((work / "conflicts.json").read_text(encoding="utf-8"))
    found = [{s["path"] for s in c["statements"]} for c in conflicts]
    for paths in expected.get("conflicts", []):
        if not any(set(paths) <= f for f in found):
            bad.append(f"conflict not reported: {paths}")
    if with_llm:
        for c in conflicts:
            for s in c["statements"]:
                if not s["verified"]:
                    bad.append(f"conflict quote not verbatim in {s['path']}: {s['quote'][:60]!r}")

    analysis = json.loads((work / "analysis.json").read_text(encoding="utf-8"))
    ids = {c["id"] for c in analysis["collisions"]}
    for ident in expected.get("collisions", []):
        if ident not in ids:
            bad.append(f"identifier collision not reported: {ident}")
    for ident in sorted(ids - set(expected.get("collisions", []))):
        bad.append(f"unexpected identifier collision: {ident}")
    anomalies = [set(a["paths"]) for a in analysis["anomalies"]]
    for paths in expected.get("anomalies", []):
        if not any(set(paths) <= a for a in anomalies):
            bad.append(f"conflicting-names group not reported: {paths}")

    staging = Path(out) / "staging"
    for path in expected.get("text_free", []):
        f = staging / (path + ".md")
        if not f.exists() or f.read_text(encoding="utf-8").split("---\n", 2)[-1].strip():
            bad.append(f"text-free document not staged with an empty body: {path}")
    for path in expected.get("historical", []):
        if not (staging / "_curated" / "historical" / path).exists():
            bad.append(f"historical copy missing: {path}")
    for path in expected.get("staging_absent", []):
        if (staging / path).exists():
            bad.append(f"should not be staged: {path}")
    if conflicts and not (staging / "_curated" / "CONFLICTS.md").exists():
        bad.append("_curated/CONFLICTS.md missing")

    if with_llm:
        reviewed = {json.loads(p.read_text(encoding="utf-8")).get("cluster_id", p.stem) for p in (work / "work" / "verdicts").glob("*.json")}
        for c in analysis["clusters"]:
            if c["id"] not in reviewed:
                bad.append(f"cluster {c['id']} has no verdict: {c['members']}")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--expected", required=True)
    ap.add_argument("--with-llm", action="store_true")
    args = ap.parse_args()
    expected = yaml.safe_load(Path(args.expected).read_text(encoding="utf-8"))
    bad = score(args.out, expected, args.with_llm)
    if bad:
        print("MISMATCHES:")
        for b in bad:
            print(f"  - {b}")
        sys.exit(1)
    print("ALL EXPECTATIONS MET")


if __name__ == "__main__":
    main()
