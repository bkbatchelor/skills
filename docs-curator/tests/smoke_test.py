#!/usr/bin/env python3
"""End-to-end smoke test for docs-curator.

    python3 make_fixtures.py DIR/corpus && python3 smoke_test.py DIR/corpus

Runs analyze, record and apply against the generated corpus (output goes to
DIR/out) and checks the proposals, the curated tree and that the sources
were not touched. Prints FAIL lines and a final `smoke: ...` line; exits 1
if anything failed. Standard library only.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CURATE = HERE.parent / "scripts" / "curate.py"
FRONTMATTER_KEYS = ["source", "source_location", "commit", "path", "sha256", "format", "revision_rank",
                    "supersedes", "duplicates_of_this", "conflicts_with"]

checks = {"total": 0, "failed": 0}


def check(name, cond, detail=""):
    checks["total"] += 1
    if not cond:
        checks["failed"] += 1
        print(f"FAIL: {name}" + (f" ({detail})" if detail else ""))
    return bool(cond)


def curate(*args):
    r = subprocess.run([sys.executable, str(CURATE), *map(str, args)], capture_output=True, text=True)
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    check(f"`{args[0]}` exits 0", r.returncode == 0, r.stderr.strip()[-300:])
    check(f"`{args[0]}` prints exactly one stdout line", len(lines) == 1, f"{len(lines)} lines")
    try:
        return json.loads(lines[-1])
    except (IndexError, ValueError):
        print(r.stderr[-1000:])
        sys.exit("smoke: cannot continue without a JSON summary")


def tree_hashes(root):
    out = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file() and ".git" not in p.relative_to(root).parts:
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def porcelain(repo):
    return subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout


def find(props, kind, method=None, has=(), lacks=()):
    """Proposals of a kind/method whose members include every file in `has`."""
    out = []
    for p in props:
        files = {m["file"] for m in p["members"]}
        if p["kind"] == kind and (method is None or p["method"] == method) \
                and all(h in files for h in has) and not any(l in files for l in lacks):
            out.append(p)
    return out


def frontmatter(path):
    text = Path(path).read_text()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return (set(re.findall(r"(?m)^([a-z0-9_]+):", m.group(1))) if m else set()), text


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    corpus = Path(sys.argv[1]).resolve()
    out = corpus.parent / "out"
    sources = {"notes": corpus / "notes", "official": corpus / "official", "shared-origin": corpus / "shared-origin"}
    before = {n: tree_hashes(p) for n, p in sources.items()}
    status_before = {n: porcelain(sources[n]) for n in ("official", "shared-origin")}
    toml = corpus / "sources.toml"

    # --- analyze ---------------------------------------------------------------
    s = curate("analyze", "--sources", toml, "--out", out)
    dec_path = out / "decisions.json"
    doc = json.loads(dec_path.read_text())
    props = doc["proposals"]
    n, o, sh = "notes:", "official:", "shared:"

    check("three sources analyzed", [x["name"] for x in s["sources"]] == ["notes", "official", "shared"])
    check("remote source was cloned", (out / "sources" / "shared" / ".git").is_dir())

    p = find(props, "duplicate", "exact", [n + "meeting-notes.md", n + "meeting-notes-backup.md"])
    check("exact-byte duplicate is a pre-accepted proposal", p and p[0]["preaccepted"] and p[0]["status"] == "accept")
    p = find(props, "duplicate", "normalized", [n + "faq.md", n + "faq-formatted.md"])
    check("normalized-text duplicate is a pre-accepted proposal", p and p[0]["preaccepted"] and p[0]["status"] == "accept")
    p = find(props, "duplicate", "near", [n + "onboarding-checklist.md", n + "new-hire-checklist.md"])
    check("near-duplicate pair is a proposed duplicate", p and p[0]["status"] == "proposed" and not p[0]["preaccepted"]
          and (p[0]["evidence"]["similarity"] or 0) >= 0.90)
    trio = [n + "decks/q3-review.md", n + "decks/q3-review.pdf", n + "decks/q3-review.pptx"]
    p = find(props, "duplicate", None, trio)
    check("pptx + pdf + md triplet is one cross-format cluster", len(p) == 1 and p[0]["evidence"]["cross_format"])
    check("md is the keeper of the triplet", p and p[0]["keeper"] == n + "decks/q3-review.md")
    p = find(props, "duplicate", None, [o + "docs/glossary.md", n + "terms.md"])
    check("cross-source duplicate keeps the priority-100 copy", p and p[0]["keeper"] == o + "docs/glossary.md")

    spec = [o + "docs/spec_v1.md", o + "docs/spec_v2.md", o + "docs/spec_final.md"]
    p = find(props, "revision", None, spec)
    check("spec v1, v2 and final form one family", len(p) == 1)
    check("spec_final.md is ranked newest", p and p[0]["keeper"] == o + "docs/spec_final.md"
          and p[0]["evidence"]["ranking"][0]["file"] == o + "docs/spec_final.md")
    p = find(props, "revision", None, [o + "docs/onboarding-guide.md", o + "docs/guide_v2.md"])
    check("renamed file is linked into its family through the rename", p and p[0]["method"] == "rename_chain")
    p = find(props, "superseded", "marker", [o + "docs/old-process.md", o + "docs/new-process.md"])
    check("DEPRECATED marker gives a pre-accepted superseded proposal",
          p and p[0]["preaccepted"] and p[0]["status"] == "accept" and p[0]["keeper"] == o + "docs/new-process.md")
    p = find(props, "revision", None, [n + "roadmap_draft.md", o + "docs/roadmap.md"])
    check("newer low-priority draft produces a review packet",
          p and p[0]["needs_review"] and p[0]["packet"] and (out / p[0]["packet"]).is_file())
    roadmap_id = p[0]["id"] if p else None

    conflict_files = lambda ps: {m["file"] for x in ps for m in x["members"]}
    cf = conflict_files(find(props, "conflict", "config_key"))
    check("application-dev vs application-prod is not a conflict",
          not (cf & {o + "config/application-dev.properties", o + "config/application-prod.properties"}))
    check("two services' application.properties are not compared",
          not (cf & {o + "services/a/application.properties", o + "services/b/application.properties"}))
    p = find(props, "conflict", "config_key", [o + "config/settings.yaml", sh + "config/settings.yaml"])
    check("same yaml in two sources, same scope, is a deterministic conflict",
          len(p) == 1 and p[0]["evidence"]["diffs"][0]["key"] == "limits.max_users" and p[0]["status"] == "proposed")
    check("config conflict suggests the priority-100 winner", p and p[0]["suggested_winner"] == o + "config/settings.yaml")
    prose = find(props, "conflict", "prose", [n + "retention-policy.md", sh + "docs/data-retention.md"])
    check("contradicting figures in two md docs produce a prose review packet",
          len(prose) == 1 and prose[0]["packet"] and (out / prose[0]["packet"]).is_file())
    prose_id = prose[0]["id"] if prose else None

    inv = json.loads((out / "inventory.json").read_text())
    check("unknown extension is reported as unhandled",
          any(u["id"] == n + "data/model.xyz" for u in inv["unhandled"]) and s["unhandled"] >= 1)
    check("YAML with an anchor is marked partial_parse and the run survived",
          any(x["id"] == o + "config/anchors.yaml" and "partial_parse" in x["note"] for x in inv["notes"]))

    # --- record ----------------------------------------------------------------
    status_map = {p["id"]: p["status"] for p in props}
    verdicts = out / "verdicts-in.json"
    verdicts.write_text(json.dumps({"verdicts": [
        {"proposal_id": prose_id, "conflict": True, "suggested_winner": sh + "docs/data-retention.md",
         "rationale": "Retention after closure is 30 days in one document and 365 days in the other.",
         "confidence": "high", "claims": [{"summary": "30 vs 365 days"}]},
        {"proposal_id": roadmap_id, "suggested_winner": o + "docs/roadmap.md",
         "rationale": "The draft says it is not approved.", "confidence": "high"}]}))
    r = curate("record", verdicts, "--out", out)
    doc = json.loads(dec_path.read_text())
    by_id = {p["id"]: p for p in doc["proposals"]}
    check("record added the verdict fields", r["recorded"] == 2 and by_id[prose_id]["verdict"]["conflict"] is True
          and by_id[prose_id]["verdict"]["suggested_winner"] == sh + "docs/data-retention.md"
          and by_id[roadmap_id]["verdict"]["rationale"])
    check("record did not change any status", {p["id"]: p["status"] for p in doc["proposals"]} == status_map)

    # --- accept the rest and apply ---------------------------------------------------
    for p in doc["proposals"]:
        if p["status"] == "proposed":
            p["status"] = "accept"
    dec_path.write_text(json.dumps(doc, indent=2))
    a = curate("apply", "--out", out)
    cur = out / "curated"
    check("apply prints the graphify command", a["next"].startswith("/graphify ") and a["next"].endswith("curated"))
    for name in ("notes", "official", "shared"):
        check(f"curated/{name}/ exists and has files", (cur / name).is_dir() and any((cur / name).rglob("*")))
    for rel, needle in (("notes/decks/kickoff.pptx.md", "Project Kickoff"), ("notes/reports/policy.docx.md", "Hotel"),
                        ("notes/reports/budget.xlsx.md", "Platform")):
        keys, text = frontmatter(cur / rel)
        check(f"{rel} has all frontmatter keys", keys >= set(FRONTMATTER_KEYS), f"missing {set(FRONTMATTER_KEYS) - keys}")
        check(f"{rel} carries the converted text", needle in text)
    check("native md is hard-linked or copied unchanged",
          (cur / "official/docs/spec_final.md").read_bytes() == (sources["official"] / "docs/spec_final.md").read_bytes())

    quarantine = json.loads((out / "quarantine.json").read_text())
    qfiles = {q["file"]: q for q in quarantine["entries"]}
    gone = [n + "terms.md", n + "decks/q3-review.pdf", n + "decks/q3-review.pptx", n + "meeting-notes-backup.md",
            o + "docs/old-process.md", o + "docs/spec_v1.md", n + "roadmap_draft.md"]
    check("quarantined files are listed with a proposal id", all(g in qfiles and qfiles[g]["proposal_id"] in by_id for g in gone),
          f"missing {[g for g in gone if g not in qfiles]}")
    absent = ["notes/terms.md", "notes/decks/q3-review.pdf.md", "notes/decks/q3-review.pptx.md", "notes/meeting-notes-backup.md",
              "official/docs/old-process.md", "official/docs/spec_v1.md", "notes/roadmap_draft.md"]
    check("quarantined files are absent from curated/", not any((cur / x).exists() for x in absent))
    check("a recorded verdict can pick a different keeper than the script",
          (cur / "official/docs/roadmap.md").exists() and n + "roadmap_draft.md" in qfiles)

    manifest = json.loads((cur / "_manifest.json").read_text())
    entries = manifest["entries"]
    listed = {e["curated_path"] for e in entries if e["curated_path"]}
    on_disk = {str(p.relative_to(cur)) for p in cur.rglob("*") if p.is_file() and p.name != "_manifest.json"}
    check("_manifest.json lists every curated file", listed == on_disk, f"{sorted(listed ^ on_disk)[:4]}")
    check("_manifest.json lists the unhandled file",
          any(e["kind"] == "unhandled" and e["path"] == "data/model.xyz" for e in entries))
    ent = {(e["source"], e["path"]): e for e in entries}
    glossary = ent[("official", "docs/glossary.md")]
    check("manifest records duplicates_of_this", n + "terms.md" in glossary["duplicates_of_this"])
    spec_entry = ent[("official", "docs/spec_final.md")]
    check("manifest records supersedes and revision_rank",
          set(spec_entry["supersedes"]) == {o + "docs/spec_v1.md", o + "docs/spec_v2.md"} and spec_entry["revision_rank"] == 1)
    ret = ent[("notes", "retention-policy.md")]
    check("conflicting documents both stay and record the conflict",
          (cur / "shared/docs/data-retention.md").exists() and len(ret["conflicts_with"]) == 1
          and ret["conflicts_with"][0]["proposal_id"] == prose_id and "365" in ret["conflicts_with"][0]["summary"])
    check("yaml config conflict stays in both sources",
          (cur / "official/config/settings.yaml").exists() and (cur / "shared/config/settings.yaml").exists()
          and ent[("shared", "config/settings.yaml")]["conflicts_with"])

    s = curate("status", "--out", out)
    check("status reports the proposals", s["proposals"] == len(props) and s["curated"] is True)

    # --- re-analyze keeps decisions, hits the cache ---------------------------------------
    near = find(props, "duplicate", "near")[0]["id"]
    doc = json.loads(dec_path.read_text())
    for p in doc["proposals"]:
        if p["id"] == near:
            p["status"] = "reject"
    dec_path.write_text(json.dumps(doc, indent=2))
    s = curate("analyze", "--sources", toml, "--out", out)
    doc = json.loads(dec_path.read_text())
    by_id = {p["id"]: p for p in doc["proposals"]}
    check("re-analyze keeps the edited status", by_id[near]["status"] == "reject")
    check("re-analyze keeps accepted statuses and verdicts",
          by_id[prose_id]["status"] == "accept" and by_id[prose_id]["verdict"] and s["kept_statuses"] == len(props))
    check("re-analyze hits the cache", s["cache_hits"] > 0 and s["cache_misses"] == 0, f"hits={s['cache_hits']} misses={s['cache_misses']}")

    # --- sources untouched --------------------------------------------------------------------
    after = {n_: tree_hashes(p) for n_, p in sources.items()}
    check("source file hashes are unchanged", after == before)
    check("git status is unchanged in both repos", {n_: porcelain(sources[n_]) for n_ in status_before} == status_before)

    if checks["failed"]:
        print(f"smoke: {checks['failed']} of {checks['total']} checks FAILED")
        sys.exit(1)
    print(f"smoke: all checks passed ({checks['total']} checks)")


if __name__ == "__main__":
    main()
