"""--scope: only listed files are hashed, extracted or staged; scope.json records why each is in."""
import json
from pathlib import Path

import pytest

from conftest import run


def make_source(root: Path):
    (root / "docs/api").mkdir(parents=True)
    (root / "docs/api/payments.md").write_text("# Payments API\n\nCard charges are retried three times.", encoding="utf-8")
    (root / "docs/api/refunds.md").write_text("# Refunds API\n\nRefunds settle within five days.", encoding="utf-8")
    (root / "docs/other.md").write_text("# Unrelated\n\nOffice party planning notes.", encoding="utf-8")
    (root / "secret.md").write_text("Out of scope content that must never be read.", encoding="utf-8")


def setup(tmp_path, scope_text):
    src, out = tmp_path / "src", tmp_path / "out"
    make_source(src)
    out.mkdir()
    (out / "config.yaml").write_text("embedding_backend: tfidf\n", encoding="utf-8")
    scope = tmp_path / "scope.yaml"
    scope.write_text(scope_text, encoding="utf-8")
    return src, out, scope


def analysis(out):
    return json.loads((out / ".docs-curator/analysis.json").read_text(encoding="utf-8"))


def test_scope_limits_inventory_and_staging(tmp_path):
    src, out, scope = setup(tmp_path, (
        "repo_sha: abc123\nfiles:\n"
        "  - path: docs/api/payments.md\n    questions: [q1]\n"
        "  - glob: 'docs/api/ref*.md'\n    questions: [q2]\n"
        "  - docs/missing.md\n"))
    run("analyze", "--source", str(src), "--out", str(out), "--scope", str(scope))
    assert {f["path"] for f in analysis(out)["files"]} == {"docs/api/payments.md", "docs/api/refunds.md"}
    sc = json.loads((out / ".docs-curator/scope.json").read_text(encoding="utf-8"))
    assert sc["repo_sha"] == "abc123"
    assert sc["files"] == {"docs/api/payments.md": {"questions": ["q1"]}, "docs/api/refunds.md": {"questions": ["q2"]}}
    assert sc["unmatched_entries"] == ["docs/missing.md"]
    cached = " ".join(p.read_text(encoding="utf-8") for p in (out / ".docs-curator/text").rglob("*.md"))
    assert "Office party" not in cached and "must never be read" not in cached
    run("apply", "--source", str(src), "--out", str(out))
    staged = {p.relative_to(out / "staging").as_posix() for p in (out / "staging").rglob("*.md") if "_curated" not in p.parts}
    assert staged == {"docs/api/payments.md", "docs/api/refunds.md"}


def test_scope_update_widens_incrementally(tmp_path):
    src, out, scope = setup(tmp_path, "files:\n  - path: docs/api/payments.md\n    questions: [q1]\n")
    run("analyze", "--source", str(src), "--out", str(out), "--scope", str(scope))
    scope.write_text("files:\n  - path: docs/api/payments.md\n    questions: [q1]\n  - path: docs/other.md\n    questions: [q3]\n", encoding="utf-8")
    run("update", "--source", str(src), "--out", str(out), "--scope", str(scope))
    changes = json.loads((out / ".docs-curator/changes.json").read_text(encoding="utf-8"))
    assert changes["added"] == ["docs/other.md"] and changes["removed"] == []


def test_scope_requires_files(tmp_path):
    src, out, scope = setup(tmp_path, "repo_sha: x\n")
    with pytest.raises(SystemExit):
        run("analyze", "--source", str(src), "--out", str(out), "--scope", str(scope))


def test_scope_respects_no_extract(tmp_path):
    src, out, scope = setup(tmp_path, "files:\n  - docs/api/*.md\n")
    run("analyze", "--source", str(src), "--out", str(out), "--scope", str(scope), "--no-extract", "docs/api/refunds.md")
    st = {f["path"]: f["status"] for f in analysis(out)["files"]}
    assert st["docs/api/refunds.md"] == "skipped"
