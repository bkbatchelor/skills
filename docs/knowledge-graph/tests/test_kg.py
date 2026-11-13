"""Unit tests for kg.py. Run: uv run --no-project --python 3.12 --with pytest --with pyyaml pytest docs/knowledge-graph/tests"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import kg  # noqa: E402

DOCS_CURATOR = HERE.parents[1] / "docs-curator"


def sh(cwd, *cmd):
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo = tmp_path / "proj"
    repo.mkdir()
    sh(repo, "git", "init", "-q", "-b", "develop")
    sh(repo, "git", "config", "user.email", "t@example.com")
    sh(repo, "git", "config", "user.name", "t")
    (repo / "docs").mkdir()
    (repo / "docs/a.md").write_text("# A\n")
    (repo / "docs/b.md").write_text("# B\n")
    (repo / "tests").mkdir()
    (repo / "tests/fixture.json").write_text("{}")
    (repo / ".gitignore").write_text("out/\n")
    sh(repo, "git", "add", ".")
    sh(repo, "git", "commit", "-qm", "init")
    (repo / "out/phi").mkdir(parents=True)
    (repo / "out/phi/app.md").write_text("patient\n")
    (repo / "out/build.md").write_text("build\n")
    root = tmp_path / "curated"
    monkeypatch.setenv("KG_CURATED_ROOT", str(root))
    monkeypatch.setenv("KG_SKILL_DOCS_CURATOR", str(DOCS_CURATOR))
    kg.cmd_init(argparse.Namespace(path=str(repo), codegraph=False))
    out = root / "proj"
    cfg = (out / "kg.yaml").read_text().replace("phi_globs: []", 'phi_globs: ["out/phi/*"]')
    (out / "kg.yaml").write_text(cfg)
    return argparse.Namespace(repo=repo, out=out, ctx=lambda: kg.Ctx(str(repo)))


# ----------------------------------------------------------------------------- gating


@pytest.mark.parametrize("branch,ok", [("develop", True), ("main", True), ("develop-adc", True),
                                       ("feature/x", False), ("developer", False)])
def test_gate_branches(env, branch, ok):
    sh(env.repo, "git", "checkout", "-qb", branch) if branch != "develop" else None
    ctx = env.ctx()
    assert kg.gate_state(ctx)["ok"] is ok
    if not ok:
        with pytest.raises(SystemExit) as e:
            kg.gate(ctx, argparse.Namespace(allow_any_branch=False), "curate")
        assert e.value.code == kg.EXIT_GATE


def test_gate_dirty_and_override(env):
    (env.repo / "docs/new.md").write_text("x")
    ctx = env.ctx()
    with pytest.raises(SystemExit) as e:
        kg.gate(ctx, argparse.Namespace(allow_any_branch=False), "apply")
    assert e.value.code == kg.EXIT_GATE
    kg.gate(ctx, argparse.Namespace(allow_any_branch=True), "apply")
    log = (env.out / ".kg/runs.jsonl").read_text()
    assert "gate_override" in log


# ----------------------------------------------------------------------------- overrides


def test_overrides_rules(env):
    (env.out / "overrides.manual.yaml").write_text(
        'overrides:\n  - path: "out/build.md"\n    action: include\n    note: "hand"\n')
    ctx = env.ctx()
    entries, stats = kg.build_overrides(ctx, kg.curate_module())
    assert entries["out/phi/app.md"] == ("exclude", "PHI (kg.yaml phi_globs)")
    assert entries["tests/fixture.json"][1] == "test fixture"
    assert entries["out/build.md"] == ("include", "hand")
    assert "docs/a.md" not in entries
    assert stats["walked"] == 5  # a.md b.md fixture.json phi/app.md build.md (.gitignore is unsupported)


def test_manual_include_of_phi_dies(env):
    (env.out / "overrides.manual.yaml").write_text(
        'overrides:\n  - path: "out/phi/app.md"\n    action: include\n')
    with pytest.raises(SystemExit):
        kg.build_overrides(env.ctx(), kg.curate_module())


def test_curate_module_missing_attr(env, tmp_path, monkeypatch):
    fake = tmp_path / "dc/scripts"
    fake.mkdir(parents=True)
    (fake / "curate.py").write_text("SUPPORTED = set()\n")
    monkeypatch.setenv("KG_SKILL_DOCS_CURATOR", str(tmp_path / "dc"))
    with pytest.raises(SystemExit):
        kg.curate_module()


# ----------------------------------------------------------------------------- PHI


def write_analysis(ctx, files, clusters=()):
    kg.write_json(ctx.work / "analysis.json", {"files": [{"path": p, "sha256": s} for p, s in files],
                                               "clusters": [{"id": i, "members": m} for i, m in clusters]})


def test_phi_purge_keeps_shared_sha(env):
    ctx = env.ctx()
    write_analysis(ctx, [("out/phi/a.pdf", "s1"), ("out/phi/b.pdf", "s2"), ("docs/b.pdf", "s2")])
    t = ctx.work / "text/v2"
    t.mkdir(parents=True)
    for s in ("s1", "s2"):
        (t / f"{s}.md").write_text("x")
    assert kg.phi_scan(ctx, ("cache",)) == [f"text cache: {t / 's1.md'}"]
    assert kg.purge_phi(ctx) == 1
    assert not (t / "s1.md").exists() and (t / "s2.md").exists()
    assert kg.phi_scan(ctx) == []


def test_phi_in_staging_and_graph_stops(env):
    ctx = env.ctx()
    (env.out / "staging/out/phi").mkdir(parents=True)
    (env.out / "staging/out/phi/app.md.md").write_text("x")
    kg.write_json(env.out / "graphify-out/graph.json",
                  {"nodes": [{"id": "n", "source_file": "out/phi/app.md.md"}], "links": []})
    hits = kg.phi_scan(ctx)
    assert any(h.startswith("staging") for h in hits) and any(h.startswith("graph.json") for h in hits)
    with pytest.raises(SystemExit) as e:
        kg.phi_gate(ctx, ("staging", "graph"), "graph prepare")
    assert e.value.code == kg.EXIT_PHI


# ----------------------------------------------------------------------------- verdicts


def setup_clusters(ctx, old_members, new_members, verdict, new_id="new1", old_id="old1", moves=()):
    files = {m: f"sha-{m}" for m in old_members}
    write_analysis(ctx, list(files.items()), [(old_id, old_members)])
    kg.register_analysis(ctx, kg.read_json(ctx.work / "analysis.json"))
    cur = {m: f"sha-{m}" for m in new_members}
    for old, new in moves:
        cur[new] = f"sha-{old}"
    write_analysis(ctx, list(cur.items()), [(new_id, new_members)])
    kg.write_json(ctx.work / f"work/verdicts/{old_id}.json", verdict)
    kg.write_json(ctx.work / f"work/queue/{new_id}.json", {"cluster_id": new_id})
    return kg.read_json(ctx.work / "analysis.json")


VERDICT = {"cluster_id": "old1", "reviewed": True,
           "revisions": [{"superseded": "d/m1", "superseded_by": "d/m2", "confidence": 0.9}],
           "conflicts": [{"topic": "t", "statements": [{"path": "d/m3", "quote": "a"}, {"path": "d/m4", "quote": "b"}]}]}


def test_carry_forward_above_threshold(env):
    ctx = env.ctx()
    old = [f"d/m{i}" for i in range(1, 10)]
    new = old + ["d/new"]  # 9/10 = 0.9
    an = setup_clusters(ctx, old, new, VERDICT)
    res = kg.carry_forward(ctx, an)
    assert [c["cluster"] for c in res["carried"]] == ["new1"]
    v = kg.read_json(ctx.work / "work/verdicts/new1.json")
    assert v["cluster_id"] == "new1" and v["revisions"] and v["conflicts"]
    assert v["carried_forward"]["new_members"] == ["d/new"] and v["carried_forward"]["review_done"] is False
    assert kg.archive_stale(ctx) == ["old1"]
    assert (ctx.work / "work/verdicts-stale/old1.json").exists()
    rs = kg.review_state(ctx)
    assert rs["needs_verdict"] == [] and rs["needs_recheck"][0]["cluster"] == "new1"


def test_carry_forward_below_threshold(env):
    ctx = env.ctx()
    old = [f"d/m{i}" for i in range(1, 5)]
    new = old[:3] + ["d/x", "d/y"]  # 3/6
    an = setup_clusters(ctx, old, new, VERDICT)
    res = kg.carry_forward(ctx, an)
    assert res["carried"] == [] and res["below_threshold"][0]["overlap"] == 0.5
    assert kg.review_state(ctx)["needs_verdict"] == ["new1"]


def test_carry_forward_follows_moves_and_drops_dead_claims(env):
    ctx = env.ctx()
    old = [f"d/m{i}" for i in range(1, 6)]
    new = ["d/m1", "d/m2", "d/m3", "e/m4", "d/m6"]  # m4 moved, m5 removed, m6 added -> 4/6
    an = setup_clusters(ctx, old, new, VERDICT, moves=[("d/m4", "e/m4")])
    (env.out / "kg.yaml").write_text((env.out / "kg.yaml").read_text().replace("verdict_overlap: 0.8", "verdict_overlap: 0.6"))
    ctx = env.ctx()
    res = kg.carry_forward(ctx, an)
    assert res["carried"]
    v = kg.read_json(ctx.work / "work/verdicts/new1.json")
    assert v["conflicts"][0]["statements"][1]["path"] == "e/m4"
    assert v["carried_forward"]["moved"] == {"d/m4": "e/m4"}


def test_restore_same_id_from_stale(env):
    ctx = env.ctx()
    write_analysis(ctx, [("a", "1")], [("c1", ["a"])])
    kg.write_json(ctx.work / "work/verdicts-stale/c1.json", {"cluster_id": "c1", "reviewed": True})
    kg.write_json(ctx.work / "work/queue/c1.json", {})
    res = kg.carry_forward(ctx, kg.read_json(ctx.work / "analysis.json"))
    assert res["restored"] == ["c1"] and (ctx.work / "work/verdicts/c1.json").exists()


# ----------------------------------------------------------------------------- graph


def graph(nodes):
    return {"nodes": [{"id": i, "source_file": f, "label": i, **({"community_name": c} if c else {})}
                      for i, f, c in nodes], "links": []}


def make_plan(ctx, changed, deleted=()):
    snap = kg.snapshot(ctx, "test")
    kg.write_json(ctx.kgdir / "graph-plan.json", {"snapshot": snap.name, "changed": list(changed), "deleted": list(deleted)})
    return snap


def test_graph_check(env):
    ctx = env.ctx()
    g = ctx.out / "graphify-out"
    kg.write_json(g / "graph.json", graph([("a1", "a.md", None), ("b1", "b.md", None), ("c1", "c.md", None)]))
    make_plan(ctx, changed=["a.md"], deleted=["c.md"])
    kg.write_json(g / ".graphify_extract.json", graph([("a2", "a.md", None), ("b2", "b.md", None)]))
    rc = kg.cmd_graph_check(argparse.Namespace(repo=str(env.repo), new=None))
    res = kg.read_json(ctx.kgdir / "graph-check.json")
    assert res["explained"] == 2 and [u["id"] for u in res["unexplained"]] == ["b1"] and rc == kg.EXIT_REVIEW
    kg.write_json(g / ".graphify_extract.json", graph([("a2", "a.md", None), ("b1", "b.md", None)]))
    assert kg.cmd_graph_check(argparse.Namespace(repo=str(env.repo), new=None)) == 0


def test_graph_labels(env):
    ctx = env.ctx()
    g = ctx.out / "graphify-out"
    kg.write_json(g / "graph.json", graph([("a", "x", "Alpha"), ("b", "x", "Alpha"), ("c", "x", "Beta"),
                                           ("d", "x", "Alpha"), ("e", "x", "Gamma"), ("f", "x", "Delta")]))
    make_plan(ctx, changed=[])
    kg.write_json(g / ".graphify_analysis.json", {"communities": {"0": ["a", "b", "c"], "1": ["d", "new"],
                                                                  "2": ["e", "f"], "3": ["new2"]}})
    kg.cmd_graph_labels(argparse.Namespace(repo=str(env.repo)))
    out = kg.read_json(ctx.kgdir / "labels-proposed.json")
    assert out["carried"]["0"] == "Alpha" and out["carried"]["1"] == "Alpha (2)"
    assert out["carried"]["2"] in ("Gamma", "Delta")  # 1 of 2 = 0.5 agreement
    assert "3" in out["needs_name"]


def test_cost_estimate():
    assert kg.avg_tokens_per_file({"runs": [{"input_tokens": 100, "files": 2}, {"input_tokens": 300, "files": 2}]}) == 100
    assert kg.avg_tokens_per_file({}) is None


# ----------------------------------------------------------------------------- snapshots / links


def test_snapshot_retention_and_restore(env, monkeypatch):
    ctx = env.ctx()
    g = ctx.out / "graphify-out/graph.json"
    names = []
    for i in range(5):
        kg.write_json(g, {"v": i})
        monkeypatch.setattr(kg, "now_ts", lambda i=i: f"2026010{i}T000000")
        names.append(kg.snapshot(ctx, f"s{i}").name)
    assert [s.name for s in kg.snapshots(ctx)] == names[-3:]
    kg.write_json(g, {"v": 99})
    kg.cmd_restore(argparse.Namespace(repo=str(env.repo), timestamp=names[2], only=None, yes=True))
    assert kg.read_json(g) == {"v": 2}


def test_links_home_form(env):
    ctx = env.ctx()
    (ctx.out / "graphify-out").mkdir(exist_ok=True)
    msg = kg.place_link(ctx.repo / "graphify-out", ctx.out / "graphify-out")
    assert msg.startswith("created")
    assert kg.place_link(ctx.repo / "graphify-out", ctx.out / "graphify-out").startswith("ok")
    (ctx.repo / "x").mkdir()
    with pytest.raises(SystemExit):
        kg.place_link(ctx.repo / "x", ctx.out / "graphify-out")


def test_config_validation(env):
    (env.out / "kg.yaml").write_text((env.out / "kg.yaml").read_text() + "\nbogus: 1\n")
    with pytest.raises(SystemExit):
        env.ctx()


def test_keeper_problems(env):
    ctx = env.ctx()
    rows = [{"run_id": "r1", "path": "docs/a.md", "action": "exclude", "reason": "exact_duplicate", "kept_instead": "out/build.md"},
            {"run_id": "r1", "path": "out/build.md", "action": "exclude", "reason": "override_exclude", "kept_instead": None},
            {"run_id": "r0", "path": "old", "action": "exclude", "kept_instead": "out/build.md"},
            # chain that ends in a staged revision: fine
            {"run_id": "r1", "path": "f/dup.pdf", "action": "exclude", "reason": "exact_duplicate", "kept_instead": "f/v1.pdf"},
            {"run_id": "r1", "path": "f/v1.pdf", "action": "exclude", "reason": "superseded", "kept_instead": "f/v2.pdf"},
            {"run_id": "r1", "path": "f/v2.pdf", "action": "include", "kept_instead": None},
            # keeper excluded, but the same bytes are staged under another path (an include override): fine
            {"run_id": "r1", "path": "g/copy.pdf", "action": "exclude", "reason": "exact_duplicate", "kept_instead": "out/build.md", "sha256": "S"},
            {"run_id": "r1", "path": "g/orig.pdf", "action": "include", "reason": "override_include", "kept_instead": None, "sha256": "S"}]
    (ctx.work).mkdir(parents=True, exist_ok=True)
    (ctx.work / "decisions.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    probs = kg.keeper_problems(ctx)
    assert [p["path"] for p in probs] == ["docs/a.md"] and probs[0]["chain_ends"] == "out/build.md"


def test_fix_manifest_anchor(env):
    ctx = env.ctx()
    (ctx.out / "staging/docs").mkdir(parents=True)
    (ctx.out / "staging/docs/a.md").write_text("x")
    kg.write_json(ctx.out / "graphify-out/manifest.json",
                  {"docs/a.md": {"h": 1}, "staging/docs/b.md": {"h": 2}, "gone.md": {"h": 3}})
    assert kg.fix_manifest_anchor(ctx) == 1
    m = kg.read_json(ctx.out / "graphify-out/manifest.json")
    assert set(m) == {"staging/docs/a.md", "staging/docs/b.md", "gone.md"}
    assert kg.fix_manifest_anchor(ctx) == 0


def test_phi_decisions_only_staged_actions(env):
    ctx = env.ctx()
    ctx.work.mkdir(parents=True, exist_ok=True)
    rows = [{"run_id": "r", "path": "out/phi/a.pdf", "action": "unreadable"},
            {"run_id": "r", "path": "out/phi/b.pdf", "action": "exclude"},
            {"run_id": "r", "path": "out/phi/c.pdf", "action": "convert"}]
    (ctx.work / "decisions.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    assert kg.phi_scan(ctx, ("staging",)) == ["decisions.jsonl: out/phi/c.pdf is convert"]


def test_auto_close(env):
    ctx = env.ctx()
    write_analysis(ctx, [("docs/a.md", "1"), ("out/build.md", "2"), ("docs/b.md", "3")],
                   [("c1", ["docs/a.md", "out/build.md"]), ("c2", ["docs/a.md", "docs/b.md"])])
    (ctx.out / "overrides.yaml").write_text('overrides:\n  - path: "out/build.md"\n    action: exclude\n')
    for c in ("c1", "c2"):
        kg.write_json(ctx.work / f"work/queue/{c}.json", {})
    assert kg.auto_close(ctx, kg.read_json(ctx.work / "analysis.json")) == ["c1"]
    assert kg.read_json(ctx.work / "work/verdicts/c1.json")["kg_auto"]
    assert kg.review_state(ctx)["needs_verdict"] == ["c2"]


def test_auto_close_reopens_after_include(env):
    ctx = env.ctx()
    write_analysis(ctx, [("docs/a.md", "1"), ("out/build.md", "2")], [("c1", ["docs/a.md", "out/build.md"])])
    kg.write_json(ctx.work / "work/queue/c1.json", {})
    (ctx.out / "overrides.yaml").write_text('overrides:\n  - path: "out/build.md"\n    action: exclude\n')
    an = kg.read_json(ctx.work / "analysis.json")
    assert kg.auto_close(ctx, an) == ["c1"]
    # the rules change: out/build.md is now included, so the cluster needs a real review again
    (ctx.out / "overrides.yaml").write_text('overrides:\n  - path: "out/build.md"\n    action: include\n')
    assert kg.reopen_auto(ctx, an) == ["c1"]
    assert kg.review_state(ctx)["needs_verdict"] == ["c1"]
    # a hand-written verdict is never reopened
    kg.write_json(ctx.work / "work/verdicts/c1.json", {"cluster_id": "c1", "reviewed": True})
    assert kg.reopen_auto(ctx, an) == []


def test_snapshot_dedup_and_pin(env, monkeypatch):
    ctx = env.ctx()
    g = ctx.out / "graphify-out/graph.json"
    kg.write_json(g, {"v": "good"})
    monkeypatch.setattr(kg, "now_ts", lambda: "20260101T000000")
    good = kg.snapshot(ctx, "before graph")
    assert kg.snapshot(ctx, "retry").name == good.name  # unchanged state: no new snapshot
    kg.write_json(ctx.kgdir / "graph-plan.json", {"snapshot": good.name, "changed": [], "deleted": []})
    for i in range(5):  # failed retries, each with a different broken graph
        kg.write_json(g, {"v": f"broken{i}"})
        monkeypatch.setattr(kg, "now_ts", lambda i=i: f"2026010{i + 2}T000000")
        kg.snapshot(ctx, "before curate")
    names = [s.name for s in kg.snapshots(ctx)]
    assert good.name in names and len(names) == 4  # newest 3 plus the pinned pre-run snapshot


def test_snapshot_keeps_decisions(env):
    ctx = env.ctx()
    ctx.work.mkdir(parents=True, exist_ok=True)
    (ctx.work / "decisions.jsonl").write_text('{"run_id": "r1", "path": "a", "action": "include"}\n')
    snap = kg.snapshot(ctx, "before curate")
    assert (snap / ".docs-curator/decisions.jsonl").read_text().startswith('{"run_id": "r1"')


def set_graph_excludes(env, pats):
    import yaml
    cfg = yaml.safe_load((env.out / "kg.yaml").read_text())
    cfg["graph"]["excludes"] = pats
    (env.out / "kg.yaml").write_text(yaml.safe_dump(cfg))
    return env.ctx()


def test_sync_graph_excludes(env):
    ctx = env.ctx()
    assert kg.sync_graph_excludes(ctx) is False  # unset: graphify's file left alone
    kg.write_json(ctx.out / "graphify-out/.graphify_build.json", {"excludes": ["old/a.md"], "gitignore": True})
    ctx = set_graph_excludes(env, ["*.xlsx.md", "!/docs/keep.xlsx.md"])
    assert kg.sync_graph_excludes(ctx) is True
    b = kg.read_json(ctx.out / "graphify-out/.graphify_build.json")
    assert b == {"excludes": ["*.xlsx.md", "!/docs/keep.xlsx.md"], "gitignore": True}
    assert kg.sync_graph_excludes(ctx) is False  # idempotent


def test_bad_graph_excludes_rejected(env):
    import yaml
    cfg = yaml.safe_load((env.out / "kg.yaml").read_text())
    cfg["graph"]["excludes"] = "*.xlsx.md"
    (env.out / "kg.yaml").write_text(yaml.safe_dump(cfg))
    with pytest.raises(SystemExit):
        env.ctx()


def test_newly_excluded_sources_and_check(env):
    ctx = env.ctx()
    st = ctx.out / "staging/docs"
    st.mkdir(parents=True)
    for f in ("a.md", "form.pdf.md"):
        (st / f).write_text("x\n")
    g = ctx.out / "graphify-out"
    kg.write_json(g / "graph.json", graph([("a1", "docs/a.md", None), ("f1", "docs/form.pdf.md", None),
                                           ("gone", "docs/deleted.md", None)]))
    # form.pdf.md still exists but is no longer scanned; deleted.md is gone and never in the manifest
    assert kg.newly_excluded_sources(ctx, ["docs/a.md"]) == ["docs/deleted.md", "docs/form.pdf.md"]
    snap = kg.snapshot(ctx, "before graph")
    kg.write_json(ctx.kgdir / "graph-plan.json", {"snapshot": snap.name, "changed": [], "deleted": ["docs/deleted.md"],
                                                  "excluded": ["docs/form.pdf.md"]})
    kg.write_json(g / ".graphify_extract.json", graph([("a1", "docs/a.md", None)]))
    assert kg.cmd_graph_check(argparse.Namespace(repo=str(env.repo), new=None)) == 0
    assert kg.read_json(ctx.kgdir / "graph-check.json")["explained"] == 2


def test_run_curate_passes_no_extract(env, monkeypatch):
    ctx = env.ctx()
    seen = []
    monkeypatch.setattr(kg, "run", lambda cmd, **kw: seen.append([str(c) for c in cmd]))
    kg.run_curate(ctx, "update")
    assert seen[-1][-2:] == ["--no-extract", "out/phi/*"]  # this checkout of docs-curator supports it
    kg.run_curate(ctx, "apply")
    assert "--no-extract" not in seen[-1]


def test_carry_forward_subset_below_threshold(env):
    ctx = env.ctx()
    old = [f"d/m{i}" for i in range(1, 9)]
    new = old[:3]  # 3/8 overlap, but nothing was added: the old verdict covers every member
    an = setup_clusters(ctx, old, new, VERDICT)
    res = kg.carry_forward(ctx, an)
    assert [c["cluster"] for c in res["carried"]] == ["new1"] and not res["below_threshold"]
    v = kg.read_json(ctx.work / "work/verdicts/new1.json")
    assert v["carried_forward"]["review_done"] is True and v["carried_forward"]["new_members"] == []
    assert v["revisions"] and v["conflicts"] == []  # the m3/m4 conflict lost m4, so it is dropped
    assert kg.review_state(ctx)["needs_verdict"] == []


def test_readme_example_kg_yaml_is_valid():
    import re
    import yaml
    md = (HERE.parent / "README.md").read_text(encoding="utf-8")
    block = re.search(r"## Example kg.yaml.*?```yaml\n(.*?)```", md, re.S).group(1)
    cfg = kg.validate_config(yaml.safe_load(block), "README example")
    assert cfg["graph"]["excludes"] and cfg["related_repos"][0]["name"]


def test_subset_carry_limited_to_small_fully_read(env):
    ctx = env.ctx()
    big = [f"d/m{i}" for i in range(1, 31)]  # 30 members > subset_max_members (25)
    an = setup_clusters(ctx, big, big[:3], VERDICT)
    assert kg.carry_forward(ctx, an)["carried"] == []
    assert kg.review_state(ctx)["needs_verdict"] == ["new1"]


def test_subset_carry_skips_partial_read(env):
    ctx = env.ctx()
    old = [f"d/m{i}" for i in range(1, 9)]
    an = setup_clusters(ctx, old, old[:3], {**VERDICT, "partial_read": True})
    assert kg.carry_forward(ctx, an)["carried"] == []


def test_restamp_newline_only(env):
    import hashlib
    ctx = env.ctx()
    st = ctx.out / "staging/docs"
    st.mkdir(parents=True)
    (st / "same.md").write_text("body\n")      # old content was "body"
    (st / "edited.md").write_text("new body\n")  # old content was "body" too, but text changed
    old = hashlib.md5(b"body").hexdigest()
    kg.write_json(ctx.out / "graphify-out/manifest.json", {
        "staging/docs/same.md": {"mtime": 1, "ast_hash": old, "semantic_hash": old},
        "staging/docs/edited.md": {"mtime": 1, "ast_hash": old, "semantic_hash": old}})
    assert kg.restamp_newline_only(ctx) == ["docs/same.md"]
    m = kg.read_json(ctx.out / "graphify-out/manifest.json")
    assert m["staging/docs/same.md"]["semantic_hash"] == hashlib.md5(b"body\n").hexdigest()
    assert m["staging/docs/edited.md"]["semantic_hash"] == old  # a real change still re-extracts
    assert kg.restamp_newline_only(ctx) == []


def test_graph_labels_unique_with_existing_suffixes(env):
    ctx = env.ctx()
    g = ctx.out / "graphify-out"
    kg.write_json(g / "graph.json", graph([("a", "x", "Epic G"), ("b", "x", "Epic G"), ("c", "x", "Epic G (2)"),
                                           ("d", "x", "Epic G (2)"), ("e", "x", "Epic G")]))
    make_plan(ctx, changed=[])
    kg.write_json(g / ".graphify_analysis.json", {"communities": {"0": ["a", "b"], "1": ["c", "d"], "2": ["e"]}})
    kg.cmd_graph_labels(argparse.Namespace(repo=str(env.repo)))
    carried = kg.read_json(ctx.kgdir / "labels-proposed.json")["carried"]
    assert sorted(carried.values()) == ["Epic G", "Epic G (2)", "Epic G (3)"]
