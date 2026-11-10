"""Requirement-vs-ADR checks on a small corpus of their own (the shared corpus's clustering cut must not move)."""
import json

import pytest
import yaml

import curate
from conftest import run

REQ1 = """---
type: requirement
id: REQ-1
version: 2
---
# Payment retries
The order system must retry failed payment submissions up to 10 times before giving up on the order.
"""
ADR7 = """---
type: adr
id: ADR-7
status: accepted
satisfies: REQ-1
---
# ADR 7: Payment retries
Payment retries are capped at 3 attempts so that a failing gateway is not flooded with duplicate charges.
"""
REQ2 = "# Invoice export\n\nCustomers must be able to export their invoices as PDF files from the account page.\n"
NOTE = "# Office plants\n\nThe plants on the third floor are watered on Mondays and Thursdays by the facilities team.\n"


@pytest.fixture()
def run_dir(tmp_path):
    src, out = tmp_path / "src", tmp_path / "out"
    for rel, text in {"docs/retries.md": REQ1, "adr/0007-retries.md": ADR7, "requirements/invoice-export.md": REQ2,
                      "notes/plants.md": NOTE}.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    out.mkdir()
    (out / "config.yaml").write_text(yaml.safe_dump({
        "embedding_backend": "tfidf", "adr_globs": ["adr/*"], "requirement_globs": ["requirements/*"]}), encoding="utf-8")
    run("analyze", "--source", str(src), "--out", str(out))
    return src, out


def queue(out):
    return [json.loads(f.read_text(encoding="utf-8")) for f in (out / ".docs-curator/work/queue").glob("*.json")]


def test_explicit_ids_pair_a_requirement_with_its_adr(run_dir):
    _, out = run_dir
    items = [q for q in queue(out) if q["decision_check"]]
    assert len(items) == 1
    by_path = {m["path"]: m for m in items[0]["members"]}
    assert by_path["docs/retries.md"]["doc_type"] == "requirement" and by_path["docs/retries.md"]["type_source"] == "front_matter"
    assert by_path["adr/0007-retries.md"]["doc_status"] == "accepted"


def test_glob_typed_requirement_without_an_adr_is_unlinked(run_dir):
    _, out = run_dir
    analysis = json.loads((out / ".docs-curator/analysis.json").read_text(encoding="utf-8"))
    assert [(u["path"], u["type"], u["type_source"]) for u in analysis["unlinked"]] == [("requirements/invoice-export.md", "requirement", "path")]


def test_conflict_and_gap_verdicts_reach_the_outputs(run_dir):
    src, out = run_dir
    cid = next(q["cluster_id"] for q in queue(out) if q["decision_check"])
    verdict = {"cluster_id": cid, "reviewed": True, "decision_checks": [
        {"kind": "conflict", "topic": "Retry limit", "adr_status": "accepted", "requirement_version": "2",
         "requirement": {"path": "docs/retries.md", "quote": "retry failed payment submissions up to 10 times"},
         "adr": {"path": "adr/0007-retries.md", "quote": "capped at 3 attempts"},
         "rationale": "10 retries cannot fit a cap of 3."},
        {"kind": "gap", "topic": "No audit trail",
         "requirement": {"path": "docs/retries.md", "quote": "this sentence is not in the document"}},
    ], "doc_type_guesses": [{"path": "notes/plants.md", "type": "requirement"}]}
    (out / ".docs-curator/work/verdicts").mkdir(parents=True, exist_ok=True)
    (out / ".docs-curator/work/verdicts" / f"{cid}.json").write_text(json.dumps(verdict), encoding="utf-8")
    run("apply", "--source", str(src), "--out", str(out))
    conflicts = (out / "staging/_curated/CONFLICTS.md").read_text(encoding="utf-8")
    assert "[requirement vs ADR] Retry limit" in conflicts and "ADR status: accepted." in conflicts
    assert "[quote not verified]" not in conflicts
    report = (out / ".docs-curator/REPORT.md").read_text(encoding="utf-8")
    assert "Requirement-vs-ADR conflicts (also in `_curated/CONFLICTS.md`): 1" in report
    assert "- gap: No audit trail" in report and "[quote not verified]" in report
    assert "guessed by the reviewer" in report and "requirements/invoice-export.md" in report


def test_globs_must_be_lists(tmp_path):
    (tmp_path / "config.yaml").write_text("adr_globs: adr/*\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        curate.load_config(tmp_path)


def test_similar_topics_pair_without_ids(tmp_path):
    src, out = tmp_path / "src", tmp_path / "out"
    for rel, text in {"docs/retries.md": REQ1.replace("id: REQ-1\n", ""), "adr/0007-retries.md": ADR7.replace("satisfies: REQ-1\n", ""),
                      "notes/plants.md": NOTE, "notes/parking.md": "# Parking\n\nVisitor parking is limited to two hours in the front lot.\n"}.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    out.mkdir()
    (out / "config.yaml").write_text(yaml.safe_dump({"embedding_backend": "tfidf", "cross_type_threshold": 0.15}), encoding="utf-8")
    run("analyze", "--source", str(src), "--out", str(out))
    assert [sorted(m["path"] for m in q["members"]) for q in queue(out) if q["decision_check"]] == [["adr/0007-retries.md", "docs/retries.md"]]
