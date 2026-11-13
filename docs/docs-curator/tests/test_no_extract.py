"""--no-extract (files hashed but never opened) and trailing newlines on staged files."""
import json
from pathlib import Path

from conftest import decisions, run


def make_source(root: Path):
    (root / "docs").mkdir(parents=True)
    (root / "docs/guide.md").write_text("# Guide\n\nHow the payment service retries failed card charges.", encoding="utf-8")
    (root / "docs/notes.txt").write_text("Release notes for the billing platform, version two.\n", encoding="utf-8")
    (root / "phi/apps").mkdir(parents=True)
    (root / "phi/apps/app-123.md").write_text("Applicant: Jane Example, DOB 1980-01-01, SSN 000-00-0000", encoding="utf-8")


def test_no_extract_never_opens_and_never_stages(tmp_path):
    src, out = tmp_path / "src", tmp_path / "out"
    make_source(src)
    out.mkdir()
    (out / "config.yaml").write_text("embedding_backend: tfidf\n", encoding="utf-8")
    (out / "overrides.yaml").write_text(
        'overrides:\n  - path: "phi/apps/app-123.md"\n    action: include\n    note: "must not win"\n', encoding="utf-8")
    run("analyze", "--source", str(src), "--out", str(out), "--no-extract", "phi/*")

    an = json.loads((out / ".docs-curator/analysis.json").read_text(encoding="utf-8"))
    rec = next(f for f in an["files"] if f["path"] == "phi/apps/app-123.md")
    assert rec["status"] == "skipped" and rec["sha256"]
    cached = {p.stem for p in (out / ".docs-curator/text").rglob("*.md")}
    assert rec["sha256"] not in cached  # its text was never extracted

    run("apply", "--source", str(src), "--out", str(out))
    action, reason, _ = decisions(out)["phi/apps/app-123.md"]
    assert (action, reason) == ("exclude", "no_extract")  # the include override cannot rescue it
    assert not (out / "staging/phi").exists()

    # every staged text file ends with a newline, including sources that did not
    for f in (out / "staging").rglob("*.md"):
        assert f.read_text(encoding="utf-8").endswith("\n"), f


def test_update_keeps_no_extract(tmp_path):
    src, out = tmp_path / "src", tmp_path / "out"
    make_source(src)
    out.mkdir()
    (out / "config.yaml").write_text("embedding_backend: tfidf\n", encoding="utf-8")
    run("analyze", "--source", str(src), "--out", str(out), "--no-extract", "phi/*")
    (src / "phi/apps/app-456.md").write_text("Applicant: John Example", encoding="utf-8")
    run("update", "--source", str(src), "--out", str(out), "--no-extract", "phi/*")
    an = json.loads((out / ".docs-curator/analysis.json").read_text(encoding="utf-8"))
    assert {f["path"]: f["status"] for f in an["files"] if f["path"].startswith("phi/")} == {
        "phi/apps/app-123.md": "skipped", "phi/apps/app-456.md": "skipped"}
