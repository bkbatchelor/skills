"""Classification pre-step and per-cluster review routing, on small corpora of their own."""
import json

import pytest
import yaml

import curate
from conftest import run

REQ = """---
id: REQ-1
version: 2
---
# Payment retries
The order system must retry failed payment submissions up to 10 times before giving up on the order.
"""
ADR = """---
id: ADR-7
status: accepted
satisfies: REQ-1
---
# ADR 7: Payment retries
Payment retries are capped at 3 attempts so that a failing gateway is not flooded with duplicate charges.
"""
POLICY = """---
type: policy
---
# Travel policy
Staff book flights through the travel desk at least fourteen days before departure.
"""
NOTE = "# Office plants\n\nThe plants on the third floor are watered on Mondays and Thursdays by the facilities team.\n"
V1 = "# Expense policy\n\nClaims must be filed within 30 days of the purchase date.\n"
V2 = "# Expense policy updated\n\nClaims must be filed within 14 days of the purchase date.\n"


def make(tmp_path, docs, cfg):
    src, out = tmp_path / "src", tmp_path / "out"
    for rel, text in docs.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    out.mkdir()
    (out / "config.yaml").write_text(yaml.safe_dump({"embedding_backend": "tfidf", **cfg}), encoding="utf-8")
    run("analyze", "--source", str(src), "--out", str(out))
    return src, out


def work(out):
    return out / ".docs-curator" / "work"


def classify_queue(out):
    return [json.loads(f.read_text(encoding="utf-8")) for f in (work(out) / "classify" / "queue").glob("*.json")]


def label_all(out, labels):
    ldir = work(out) / "classify" / "labels"
    ldir.mkdir(parents=True, exist_ok=True)
    (ldir / "b1.json").write_text(json.dumps({"batch_id": "b1", "labels": labels}), encoding="utf-8")


DOCS = {"retries.md": REQ, "adr/0007.md": ADR, "plants.md": NOTE, "travel.md": POLICY}


def test_classify_is_off_by_default(tmp_path):
    _, out = make(tmp_path, DOCS, {})
    assert classify_queue(out) == []
    assert not (work(out) / "classify" / "queue").exists() or not list((work(out) / "classify" / "queue").glob("*"))


def test_untyped_documents_are_queued_but_declared_types_are_not(tmp_path):
    _, out = make(tmp_path, DOCS, {"classify_untyped": True})
    batches = classify_queue(out)
    assert len(batches) == 1 and batches[0]["model"] == "haiku" and batches[0]["labels"] == ["requirement", "adr", "other"]
    paths = {d["path"] for d in batches[0]["docs"]}
    assert paths == {"retries.md", "adr/0007.md", "plants.md"}  # travel.md says `type: policy`
    doc = next(d for d in batches[0]["docs"] if d["path"] == "retries.md")
    assert doc["title"] == "Payment retries" and "retry failed payment" in doc["snippet"] and len(doc["sha256"]) == 64


def test_labels_type_documents_and_pair_them_for_the_decision_check(tmp_path):
    src, out = make(tmp_path, DOCS, {"classify_untyped": True})
    sha = {d["path"]: d["sha256"] for d in classify_queue(out)[0]["docs"]}
    label_all(out, [
        {"sha256": sha["retries.md"], "path": "retries.md", "type": "requirement", "confidence": 0.95},
        {"sha256": sha["adr/0007.md"], "path": "adr/0007.md", "type": "adr", "confidence": 0.9},
        {"sha256": sha["plants.md"], "path": "plants.md", "type": "other", "confidence": 0.99},
    ])
    run("analyze", "--source", str(src), "--out", str(out))
    items = [json.loads(f.read_text(encoding="utf-8")) for f in (work(out) / "queue").glob("*.json")]
    checks = [q for q in items if q["decision_check"]]
    assert len(checks) == 1
    by_path = {m["path"]: m for m in checks[0]["members"]}
    assert by_path["retries.md"]["type_source"] == "classifier" and by_path["retries.md"]["type_confidence"] == 0.95
    assert checks[0]["review"]["tier"] == "deep" and "requirement_vs_adr" in checks[0]["review"]["reasons"]
    assert classify_queue(out) == []  # everything is labelled now


def test_low_confidence_labels_are_ignored_and_not_requeued(tmp_path):
    src, out = make(tmp_path, DOCS, {"classify_untyped": True, "classify_min_confidence": 0.8})
    sha = {d["path"]: d["sha256"] for d in classify_queue(out)[0]["docs"]}
    label_all(out, [{"sha256": sha["retries.md"], "path": "retries.md", "type": "requirement", "confidence": 0.5}])
    run("analyze", "--source", str(src), "--out", str(out))
    analysis = json.loads((out / ".docs-curator" / "analysis.json").read_text(encoding="utf-8"))
    assert "retries.md" not in analysis["doc_types"]
    assert analysis["classification"]["labels_applied"] == 0
    assert "retries.md" not in {d["path"] for b in classify_queue(out) for d in b["docs"]}


def test_malformed_labels_are_skipped(tmp_path, capsys):
    src, out = make(tmp_path, DOCS, {"classify_untyped": True})
    ldir = work(out) / "classify" / "labels"
    ldir.mkdir(parents=True)
    (ldir / "bad.json").write_text("{not json", encoding="utf-8")
    label_all(out, [{"sha256": "x", "type": "contract", "confidence": 1}])
    run("analyze", "--source", str(src), "--out", str(out))
    err = capsys.readouterr().err
    assert "bad.json ignored" in err and "entry ignored" in err


def test_labels_do_nothing_when_classify_is_off(tmp_path):
    src, out = make(tmp_path, DOCS, {})
    sha = curate.sha256_file(src / "retries.md")
    label_all(out, [{"sha256": sha, "type": "requirement", "confidence": 1}])
    run("analyze", "--source", str(src), "--out", str(out))
    analysis = json.loads((out / ".docs-curator" / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["doc_types"] == {}


@pytest.mark.parametrize("key,bad", [("classify_untyped", "yes"), ("classify_min_confidence", 2), ("classify_batch_size", 0),
                                      ("review_model_deep", ""), ("deep_review_min_members", True)])
def test_bad_routing_config_is_rejected(tmp_path, key, bad):
    out = tmp_path / "out"
    out.mkdir()
    (out / "config.yaml").write_text(yaml.safe_dump({key: bad}), encoding="utf-8")
    with pytest.raises(SystemExit):
        curate.load_config(out)


# --- review routing ------------------------------------------------------------------------------------------


def queue_items(out):
    return {q["cluster_id"]: q for q in (json.loads(f.read_text(encoding="utf-8")) for f in (work(out) / "queue").glob("*.json"))}


def test_ordinary_cluster_goes_to_the_standard_model(tmp_path):
    # different file names, so there is no revision chain to be unsure about
    _, out = make(tmp_path, {"policy/expense.md": V1, "finance/reimbursement.md": V2}, {})
    (item,) = queue_items(out).values()
    assert item["review"] == {"tier": "standard", "model": "sonnet", "reasons": []}
    routing = json.loads((work(out) / "routing.json").read_text(encoding="utf-8"))
    assert routing["review"] == {"sonnet": [item["cluster_id"]]} and routing["escalate"] == []


def test_unorderable_revision_chain_goes_deep(tmp_path):
    _, out = make(tmp_path, {"policy/expense.md": V1, "policy/expense_updated.md": V2}, {})
    (item,) = queue_items(out).values()
    assert item["review"]["tier"] == "deep" and item["review"]["reasons"] == ["ambiguous_revision_chain"]


def test_large_cluster_goes_deep_and_models_are_configurable(tmp_path):
    docs = {f"policy/expense_v{i}.md": f"# Expense policy\n\nClaims must be filed within {10 + i} days of purchase, version {i}.\n" for i in range(1, 5)}
    _, out = make(tmp_path, docs, {"deep_review_min_members": 3, "review_model_deep": "fable", "review_model_standard": "haiku"})
    (item,) = queue_items(out).values()
    assert item["review"] == {"tier": "deep", "model": "fable", "reasons": item["review"]["reasons"]}
    assert "large_cluster" in item["review"]["reasons"]
    routing = json.loads((work(out) / "routing.json").read_text(encoding="utf-8"))
    assert list(routing["review"]) == ["fable"]


def test_route_review_rules():
    cfg = dict(curate.DEFAULTS)
    cl = {"members": ["a", "b"]}
    assert curate.route_review(cl, [{"deterministic": True}], False, None, cfg) == {"tier": "standard", "model": "sonnet", "reasons": []}
    assert curate.route_review(cl, [{"deterministic": False}], False, None, cfg)["reasons"] == ["ambiguous_revision_chain"]
    assert curate.route_review({"members": list("abcdef")}, [], False, None, cfg)["reasons"] == ["large_cluster"]
    deep = curate.route_review(cl, [], True, "conflict_found", cfg)
    assert deep["tier"] == "deep" and deep["model"] == "opus" and deep["reasons"] == ["requirement_vs_adr", "escalated_conflict_found"]


def test_escalation_reason():
    cfg = dict(curate.DEFAULTS)
    assert curate.escalation_reason({"review_tier": "standard", "conflicts": [{"topic": "x"}]}, cfg) == "conflict_found"
    assert curate.escalation_reason({"review_tier": "standard", "revisions": [{"confidence": 0.5}]}, cfg) == "low_confidence_revision"
    assert curate.escalation_reason({"review_tier": "standard", "revisions": [{"confidence": 0.9}]}, cfg) is None
    assert curate.escalation_reason({"review_tier": "deep", "conflicts": [{"topic": "x"}]}, cfg) is None
    assert curate.escalation_reason({"conflicts": [{"topic": "x"}]}, cfg) is None  # untiered verdicts are never re-queued


def test_standard_verdict_with_a_conflict_is_requeued_once_at_the_deep_tier(tmp_path):
    src, out = make(tmp_path, {"policy/expense.md": V1, "finance/reimbursement.md": V2}, {})
    (cid,) = queue_items(out)
    vdir = work(out) / "verdicts"
    verdict = {"cluster_id": cid, "reviewed": True, "review_tier": "standard", "model": "sonnet",
               "conflicts": [{"topic": "claim window", "statements": [], "rationale": "30 vs 14 days"}]}
    (vdir / f"{cid}.json").write_text(json.dumps(verdict), encoding="utf-8")
    run("analyze", "--source", str(src), "--out", str(out))
    item = queue_items(out)[cid]
    assert item["review"]["tier"] == "deep" and item["review"]["reasons"] == ["escalated_conflict_found"]
    routing = json.loads((work(out) / "routing.json").read_text(encoding="utf-8"))
    assert routing["escalate"] == [{"cluster_id": cid, "reason": "conflict_found"}]
    # the deep review overwrites the verdict; nothing is queued after that
    verdict.update(review_tier="deep", model="opus")
    (vdir / f"{cid}.json").write_text(json.dumps(verdict), encoding="utf-8")
    run("analyze", "--source", str(src), "--out", str(out))
    assert queue_items(out) == {}
    assert json.loads((work(out) / "routing.json").read_text(encoding="utf-8"))["escalate"] == []


def test_override_excluded_documents_are_not_queued_for_classification(tmp_path):
    src, out = tmp_path / "src", tmp_path / "out"
    for rel, text in {"docs/retries.md": REQ, "build/notes.md": NOTE}.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    out.mkdir()
    (out / "config.yaml").write_text(yaml.safe_dump({"embedding_backend": "tfidf", "classify_untyped": True}), encoding="utf-8")
    (out / "overrides.yaml").write_text(yaml.safe_dump([{"path": "build/notes.md", "action": "exclude", "note": "build output"}]), encoding="utf-8")
    run("analyze", "--source", str(src), "--out", str(out))
    assert {d["path"] for b in classify_queue(out) for d in b["docs"]} == {"docs/retries.md"}
