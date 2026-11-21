import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import bench  # noqa: E402


@pytest.fixture
def b(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    d = tmp_path / "mybench"
    bench.cmd_init(type("A", (), {"dir": str(d)}))
    cfg = (d / "bench.yaml").read_text()
    cfg = cfg.replace("  # rulesnew:\n  #   description: Every source, with a candidate instructions file\n"
                      "  #   tools: [read, graphify, codegraph]\n  #   add_dirs: [~/curated/my-repo/staging]\n"
                      "  #   instructions: candidates/new-CLAUDE.md\n",
                      "  rulesnew:\n    tools: [read, graphify, codegraph]\n    instructions: new.md\n"
                      "  rulesold:\n    tools: [read, graphify, codegraph]\n    instructions: old.md\n")
    cfg = cfg.replace("~/Projects/my-repo", str(repo)).replace("~/curated", str(tmp_path / "curated"))
    cfg = cfg.replace("~/.cache/kg-benchmark", str(tmp_path / "cache"))
    (d / "bench.yaml").write_text(cfg)
    (d / "new.md").write_text("# new\n")
    (d / "old.md").write_text("# old\n")
    return bench.Bench(d)


def test_template_is_valid(b):
    assert set(b.arms) == {"base", "kg", "cur", "rulesnew", "rulesold"}
    assert "Q01" in b.questions()


def test_bad_arm_name_rejected(b):
    cfg = (b.dir / "bench.yaml").read_text().replace("  base:", "  base-x:")
    (b.dir / "bench.yaml").write_text(cfg)
    with pytest.raises(SystemExit):
        bench.Bench(b.dir)


def test_deny_rules_use_double_slash_and_block_bench(b):
    deny = bench.deny_rules(b, "base")
    assert f"Read(/{b.dir}/**)" in deny  # `//abs` form, never a single leading slash
    assert any(r.startswith("Bash(graphify") for r in deny) and "Skill(code-graph)" in deny
    assert any("graphify-out" in r and r.startswith("Read(//") for r in deny)
    assert not any(r.startswith("Read(/") and not r.startswith("Read(//") and "**" in r and "{" not in r
                   and not r.startswith("Read(**") for r in deny)


def test_graph_arm_keeps_graph_tools(b):
    deny, allow = bench.deny_rules(b, "kg"), bench.allow_rules(b, "kg")
    assert "Bash(graphify query:*)" in allow and "Bash(codegraph node:*)" in allow
    assert not any(r.startswith("Bash(graphify") or r.startswith("Bash(codegraph") for r in deny)


def test_own_instructions_copy_not_denied(b):
    deny = bench.deny_rules(b, "rulesnew")
    own, other = str(b.instructions_copy("rulesnew").parent), str(b.instructions_copy("rulesold").parent)
    assert any(other in r for r in deny)
    assert not any(own in r for r in deny)


def test_claude_cmd_excludes_live_instructions_and_loads_copy(b):
    bench.stage_instructions(b)
    cmd, env = bench.claude_cmd(b, "rulesnew", "q")
    settings = json.loads(cmd[cmd.index("--settings") + 1])
    assert settings["claudeMdExcludes"] and env["CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD"] == "1"
    assert str(b.instructions_copy("rulesnew").parent) in cmd
    assert b.instructions_copy("rulesnew").read_text() == "# new\n"


@pytest.mark.parametrize("cmd,expected", [
    ('graphify query "x"', "docs"),
    ("(codegraph node Foo 2>&1 | head)", "code"),
    ('grep -rn foo . | grep -v graphify-out', None),
    ("grep -rn foo --exclude-dir=graphify-out .", None),
    ("cat graphify-out/graph.json", "graphfile"),
])
def test_graph_kind_ignores_exclusions(b, cmd, expected):
    assert bench.graph_kind(b, {"name": "Bash", "input": {"command": cmd}}) == expected


def test_grep_glob_exclusion_is_not_graph_use(b):
    u = {"name": "Grep", "input": {"pattern": "x", "path": "/r", "glob": "!graphify-out/**"}}
    assert bench.graph_kind(b, u) is None


def test_paired_bootstrap_is_deterministic():
    rows = [{"arm": a, "qid": f"Q{i:02d}", "c": c, "tok": 100} for i in range(1, 7)
            for a, c in (("x", 4 + (i % 2)), ("y", 4))]
    r1, r2 = bench.paired(rows, "x", "y", 1), bench.paired(rows, "x", "y", 1)
    assert r1 == r2 and r1["diff"] == 0.5 and r1["better_same_worse"] == [3, 3, 0]


def test_redact_hides_setup_words():
    text, changes = bench.redact("The docs graph and graphify say so; the curated copy agrees.", [])
    assert "graph" not in text.lower().replace("[source]", "") and changes


def test_audit_prep_and_merge(b):
    (b.dir / "answers").mkdir()
    (b.dir / "answers/Q01-kg-r1.md").write_text("graphify said ADR-9")
    (b.dir / "answers/Q01-base-r1.md").write_text("ADR-8")
    with open(b.dir / "grades.jsonl", "w") as f:
        f.write(json.dumps({"answer_file": "Q01-kg-r1.md", "qid": "Q01", "hallucinations": ["cites ADR-9"]}) + "\n")
        f.write(json.dumps({"answer_file": "Q01-base-r1.md", "qid": "Q01", "hallucinations": ["cites ADR-8"]}) + "\n")
    bench.cmd_audit_prep(type("A", (), {"bench": str(b.dir)}))
    claims = json.loads((b.dir / "audit/claims.json").read_text())
    assert len(claims) == 2 and all("kg" not in c["answer_file"] for c in claims)
    assert "graphify" not in "".join(p.read_text() for p in (b.dir / "audit/answers").glob("*.md"))
    key = json.loads((b.dir / "audit/claim-key.json").read_text())
    verdicts = [{"id": cid, "verdict": "CONFIRMED" if "kg" in af else "JUDGE_WRONG"} for cid, af in key.items()]
    (b.dir / "audit/audit.json").write_text(json.dumps(verdicts))
    bench.cmd_audit_merge(type("A", (), {"bench": str(b.dir)}))
    s = json.loads((b.dir / "audit/summary.json").read_text())
    assert s["kg"]["runs_with_confirmed_false_claim"] == 1 and s["base"]["runs_with_confirmed_false_claim"] == 0
