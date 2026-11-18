"""PDF exports beside their source, override-excluded files kept out of clusters, and clusters deferred by the cap."""
import json
from pathlib import Path

from conftest import decisions, run
from make_corpus import make_pdf

WORDS = ("alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar papa "
         "quebec romeo sierra tango uniform victor whiskey xray yankee zulu").split()


def lines(seed, n=30):
    return [f"Row {i}: " + " ".join(WORDS[(seed * 7 + i * 3 + k) % len(WORDS)] for k in range(8)) for i in range(n)]


def analysis(out):
    return json.loads((Path(out) / ".docs-curator/analysis.json").read_text(encoding="utf-8"))


def setup(tmp_path, config="embedding_backend: tfidf\n", overrides=None):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    (out / "config.yaml").write_text(config, encoding="utf-8")
    if overrides:
        (out / "overrides.yaml").write_text(overrides, encoding="utf-8")
    return src, out


def write_export_pair(src):
    """plan.md and a PDF 'export' of it whose text drifted (about a fifth of the rows mangled)."""
    body = lines(1)
    (src / "docs").mkdir(parents=True, exist_ok=True)
    (src / "docs/plan.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    mangled = [ln if i % 5 else " ".join(reversed(ln.split())) + " page footer" for i, ln in enumerate(body)]
    make_pdf(src, "docs/plan.pdf", mangled)


def test_pdf_export_below_near_duplicate_threshold_is_a_format_duplicate(tmp_path):
    src, out = setup(tmp_path)
    write_export_pair(src)
    # an unrelated PDF that only shares the name stem of a file in another folder
    (src / "notes").mkdir()
    (src / "notes/plan.md").write_text("\n".join(lines(9)) + "\n", encoding="utf-8")
    make_pdf(src, "notes/plan.pdf", [f"Ledger {i}: invoice {i * 37} settled by wire transfer on day {i % 28 + 1}"
                                     for i in range(30)])
    run("analyze", "--source", str(src), "--out", str(out))
    edge = next(e for e in analysis(out)["edges"] if {e["a"], e["b"]} == {"docs/plan.md", "docs/plan.pdf"})
    assert edge["rule"] == "pdf_export" and 0.6 <= edge["sim"] < 0.9
    assert not any({e["a"], e["b"]} == {"notes/plan.md", "notes/plan.pdf"} for e in analysis(out)["edges"])
    run("apply", "--source", str(src), "--out", str(out))
    d = decisions(out)
    assert d["docs/plan.pdf"] == ("exclude", "format_duplicate", "docs/plan.md")  # the editable source is kept
    assert d["docs/plan.md"][0] != "exclude"
    assert d["notes/plan.pdf"][0] != "exclude"


def test_pdf_export_rule_can_be_turned_off(tmp_path):
    src, out = setup(tmp_path, "embedding_backend: tfidf\nexport_duplicate_threshold: null\n")
    write_export_pair(src)
    run("analyze", "--source", str(src), "--out", str(out))
    assert not any(e.get("rule") == "pdf_export" for e in analysis(out)["edges"])


def test_override_excluded_files_stay_out_of_review_clusters(tmp_path):
    src, out = setup(tmp_path, overrides='overrides:\n  - path: "build/out.md"\n    action: exclude\n    note: "build output"\n')
    (src / "docs").mkdir()
    (src / "build").mkdir()
    base = lines(4)
    (src / "docs/a.md").write_text("\n".join(base) + "\n", encoding="utf-8")
    (src / "docs/b.md").write_text("\n".join(base[:24] + lines(5)[:6]) + "\n", encoding="utf-8")
    (src / "build/out.md").write_text("\n".join(base[:22] + lines(6)[:8]) + "\n", encoding="utf-8")
    run("analyze", "--source", str(src), "--out", str(out))
    members = {m for c in analysis(out)["clusters"] for m in c["members"]}
    assert "build/out.md" not in members
    assert {"docs/a.md", "docs/b.md"} <= members


def test_clusters_past_the_cap_are_marked_deferred(tmp_path, capsys):
    src, out = setup(tmp_path, "embedding_backend: tfidf\nmax_llm_clusters_per_run: 1\n")
    (src / "docs").mkdir()
    for topic in (2, 11):
        base = lines(topic)
        (src / f"docs/t{topic}-a.md").write_text("\n".join(base) + "\n", encoding="utf-8")
        (src / f"docs/t{topic}-b.md").write_text("\n".join(base[:24] + lines(topic + 1)[:6]) + "\n", encoding="utf-8")
    run("analyze", "--source", str(src), "--out", str(out))
    clusters = analysis(out)["clusters"]
    assert len(clusters) >= 2
    assert sum(c["queued"] for c in clusters) == 1
    assert sum(c["deferred"] for c in clusters) == len(clusters) - 1
    assert "deferred:" in capsys.readouterr().out
    state = json.loads((out / ".docs-curator/state.json").read_text(encoding="utf-8"))
    assert state["analyze"]["deferred"] == len(clusters) - 1
