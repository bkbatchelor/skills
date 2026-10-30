"""End-to-end gates on the synthetic corpus."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

import curate
import score
from conftest import EXPECTED, FIXTURES, checksums, decisions, run

SCRIPT = Path(curate.__file__)


def test_help_exits_zero_and_lists_subcommands():
    r = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "analyze" in r.stdout and "apply" in r.stdout


def test_scores_against_the_answer_key(pipeline):
    _, out, _ = pipeline
    expected = yaml.safe_load(EXPECTED.read_text(encoding="utf-8"))
    assert score.score(out, expected, with_llm=True) == []


def test_source_is_untouched(pipeline):
    corpus, _, before = pipeline
    assert checksums(corpus) == before


def test_staging_front_matter_and_pairs(pipeline):
    corpus, out, _ = pipeline
    staging = out / "staging"
    dec = decisions(out)
    assert not list(staging.rglob("*.pptx"))
    for path, (action, reason, _) in dec.items():
        if action not in ("include", "convert"):
            continue
        if path.endswith(".pptx"):
            assert (staging / (path + ".pdf")).is_file()
            sidecar = staging / (path + ".notes.md")
            meta, _, ok = curate.split_front_matter(sidecar.read_text(encoding="utf-8"))
            assert ok and {"source_path", "sha256", "status"} <= set(meta)
            continue
        name = path if path.endswith(".md") else path + ".md"
        meta, _, ok = curate.split_front_matter((staging / name).read_text(encoding="utf-8"))
        assert ok, path
        assert {"source_path", "source_format", "sha256", "status", "description"} <= set(meta), path
        assert meta["source_path"] == path and meta["status"] == (reason if reason != "unique" else "unique")
        assert "tags" not in meta


def test_staging_extensions_come_from_installed_graphify(pipeline):
    import graphify.detect as detect

    accepted = set()
    for name in dir(detect):
        if name.endswith("_EXTENSIONS") and not name.startswith("_"):
            accepted |= set(getattr(detect, name))
    assert ".md" in accepted and ".pdf" in accepted
    # stop condition: if Graphify ever accepts .pptx the staging design needs review
    assert ".pptx" not in accepted, "Graphify now supports .pptx: review the pptx -> pdf design"
    _, out, _ = pipeline
    for p in (out / "staging").rglob("*"):
        if p.is_file():
            assert p.suffix.lower() in accepted, p


def test_conflicts_and_historical_sidecars(pipeline):
    _, out, _ = pipeline
    text = (out / "staging/_curated/CONFLICTS.md").read_text(encoding="utf-8")
    assert "source_format: generated" in text and "99.9%" in text and "three days" in text
    hist = (out / "staging/_curated/historical/policy/travel_policy.md").read_text(encoding="utf-8")
    assert "status: superseded" in hist and "Antarctic" in hist


def test_pptx_notes_sidecar_carries_speaker_notes(pipeline):
    _, out, _ = pipeline
    assert "customer outage story" in (out / "staging/decks/platform_roadmap.pptx.notes.md").read_text(encoding="utf-8")


def test_source_front_matter_is_nested(pipeline):
    _, out, _ = pipeline
    meta, _, _ = curate.split_front_matter((out / "staging/engineering/coding_standards.md").read_text(encoding="utf-8"))
    assert meta["source_front_matter"]["owner"] == "platform-team"


def test_report_sections(pipeline):
    _, out, _ = pipeline
    report = (out / ".docs-curator/REPORT.md").read_text(encoding="utf-8")
    for section in ("Totals", "Excluded duplicates", "Filed under conflicting names", "Identifier collisions", "Superseded",
                    "Other exclusions", "Flagged but kept", "Unreadable", "Not ingestible", "Sidecars written into staging",
                    "LLM queue", "Staging method", "Next step"):
        assert f"## {section}" in report
    assert "/graphify" in report


def test_state_records_backend_and_config(pipeline):
    _, out, _ = pipeline
    state = json.loads((out / ".docs-curator/state.json").read_text(encoding="utf-8"))
    assert state["config"]["embedding_backend"] == "fastembed"
    assert json.loads((out / ".docs-curator/analysis.json").read_text(encoding="utf-8"))["backend"] == "fastembed"


def test_decisions_schema(pipeline):
    _, out, _ = pipeline
    rows = [json.loads(l) for l in (out / ".docs-curator/decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 35
    for r in rows:
        assert set(r) == {"run_id", "path", "sha256", "action", "reason", "kept_instead", "evidence", "confidence"}
        assert r["action"] in {"include", "exclude", "convert", "unreadable", "not_ingestible"}


def test_second_run_is_idempotent(pipeline):
    corpus, out, _ = pipeline
    first = decisions(out)
    run("analyze", "--source", str(corpus), "--out", str(out))
    state = json.loads((out / ".docs-curator/state.json").read_text(encoding="utf-8"))
    assert state["analyze"]["new_or_changed"] == 0
    run("apply", "--source", str(corpus), "--out", str(out))
    assert decisions(out) == first


def clone(pipeline, tmp_path):
    corpus, out, _ = pipeline
    dest = tmp_path / "out"
    shutil.copytree(out, dest)
    return corpus, dest


def test_override_flips_exactly_one_file(pipeline, tmp_path):
    corpus, out = clone(pipeline, tmp_path)
    before = decisions(out)
    (out / "overrides.yaml").write_text("- {path: hr/onboarding_guide.md, action: exclude, note: test}\n")
    run("apply", "--source", str(corpus), "--out", str(out))
    after = decisions(out)
    changed = {p for p in before if before[p] != after[p]}
    assert changed == {"hr/onboarding_guide.md"}
    assert after["hr/onboarding_guide.md"][:2] == ("exclude", "override_exclude")
    assert not (out / "staging/hr/onboarding_guide.md").exists()


def test_override_include_rescues_a_superseded_file(pipeline, tmp_path):
    corpus, out = clone(pipeline, tmp_path)
    (out / "overrides.yaml").write_text("- {path: projects/atlas/design_spec.md, action: include}\n")
    run("apply", "--source", str(corpus), "--out", str(out))
    assert decisions(out)["projects/atlas/design_spec.md"][:2] == ("include", "override_include")
    assert (out / "staging/projects/atlas/design_spec.md").exists()


def test_near_duplicate_exclude_is_opt_in(pipeline, tmp_path):
    corpus, out = clone(pipeline, tmp_path)
    before = decisions(out)
    (out / "config.yaml").write_text("near_duplicate_action: exclude\n")
    run("apply", "--source", str(corpus), "--out", str(out))
    after = decisions(out)
    assert {p for p in before if before[p] != after[p]} == {"notes/release_notes_edited.md"}
    assert after["notes/release_notes_edited.md"][:2] == ("exclude", "near_duplicate")


def test_missing_verdicts_mean_keep(pipeline, tmp_path):
    corpus, out = clone(pipeline, tmp_path)
    for f in (out / ".docs-curator/work/verdicts").glob("*.json"):
        f.unlink()
    run("apply", "--source", str(corpus), "--out", str(out))
    dec = decisions(out)
    assert dec["finance/headcount_plan_2024.xlsx"][:2] == ("include", "unique")  # needed a verdict
    assert dec["projects/atlas/design_spec.md"][:2] == ("exclude", "superseded")  # two agreeing signals, no verdict needed
    assert not (out / "staging/_curated/CONFLICTS.md").exists()
    assert not (out / "staging/_curated/historical").exists()


def test_queue_cap_defers_the_rest(pipeline, tmp_path):
    corpus, out = clone(pipeline, tmp_path)
    shutil.rmtree(out / ".docs-curator/work/verdicts")
    (out / "config.yaml").write_text("max_llm_clusters_per_run: 2\n")
    run("analyze", "--source", str(corpus), "--out", str(out))
    queue = list((out / ".docs-curator/work/queue").glob("*.json"))
    assert len(queue) == 2
    sizes = sorted((len(json.loads(q.read_text(encoding="utf-8"))["members"]) for q in queue), reverse=True)
    assert sizes[0] == 3  # largest cluster first
    item = json.loads(queue[0].read_text(encoding="utf-8"))
    assert {"cluster_id", "members", "chains", "near_duplicate_pairs"} <= set(item)
    assert {"path", "text_path", "size_bytes", "revision_signals"} <= set(item["members"][0])
    run("apply", "--source", str(corpus), "--out", str(out))
    assert "deferred past max_llm_clusters_per_run" in (out / ".docs-curator/REPORT.md").read_text(encoding="utf-8")


def test_verdicts_persist_across_analyze(pipeline, tmp_path):
    corpus, out = clone(pipeline, tmp_path)
    run("analyze", "--source", str(corpus), "--out", str(out))
    assert not list((out / ".docs-curator/work/queue").glob("*.json"))  # all clusters already reviewed


def test_update_reports_added_modified_and_removed(pipeline, tmp_path):
    corpus, out = clone(pipeline, tmp_path)
    src = tmp_path / "src"
    shutil.copytree(corpus, src)
    run("analyze", "--source", str(src), "--out", str(out))
    (src / "hr/onboarding_guide.md").write_text("Rewritten onboarding guide with new content about laptops and badges.\n" * 20)
    (src / "brand_new_note.md").write_text("A brand new note about parking permits and visitor passes.\n" * 20)
    victim = next(p for p in sorted(src.rglob("*.txt")))
    gone = victim.relative_to(src).as_posix()
    victim.unlink()
    run("update", "--source", str(src), "--out", str(out))
    changes = json.loads((out / ".docs-curator/changes.json").read_text(encoding="utf-8"))
    assert changes["added"] == ["brand_new_note.md"]
    assert changes["modified"] == ["hr/onboarding_guide.md"]
    assert changes["removed"] == [gone]
    run("apply", "--source", str(src), "--out", str(out))
    assert (out / "staging/brand_new_note.md").is_file()


def test_update_requires_an_earlier_analysis(corpus, tmp_path):
    with pytest.raises(SystemExit):
        run("update", "--source", str(corpus), "--out", str(tmp_path / "out"))


def test_refuses_out_inside_source(corpus):
    with pytest.raises(SystemExit):
        run("analyze", "--source", str(corpus), "--out", str(corpus / "out"))
    assert not (corpus / "out").exists()


def test_apply_detects_a_changed_source(corpus, tmp_path):
    src = tmp_path / "src"
    shutil.copytree(corpus, src)
    out = tmp_path / "out"
    run("analyze", "--source", str(src), "--out", str(out))
    (src / "hr/onboarding_guide.md").write_text("changed\n")
    with pytest.raises(SystemExit):
        run("apply", "--source", str(src), "--out", str(out))


def test_tfidf_backend_runs(corpus, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "config.yaml").write_text("embedding_backend: tfidf\n")
    run("analyze", "--source", str(corpus), "--out", str(out))
    run("apply", "--source", str(corpus), "--out", str(out))
    dec = decisions(out)
    assert dec["decks/platform_roadmap.pdf"][1] == "format_duplicate"
    assert json.loads((out / ".docs-curator/analysis.json").read_text(encoding="utf-8"))["backend"] == "tfidf"


def test_unloadable_embedding_model_stops_the_run(corpus, tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "config.yaml").write_text("embedding_model: no/such-model-here\n")
    with pytest.raises(SystemExit) as exc:
        run("analyze", "--source", str(corpus), "--out", str(out))
    assert exc.value.code != 0


def test_fixture_cluster_ids_match_the_current_corpus(pipeline):
    """Fixtures are named after cluster ids; this fails loudly when the corpus changes them."""
    _, out, _ = pipeline
    analysis = json.loads((out / ".docs-curator/analysis.json").read_text(encoding="utf-8"))
    ids = {c["id"] for c in analysis["clusters"]}
    assert {f.stem for f in FIXTURES.glob("*.json")} == ids


def test_link_points_source_graphify_out_at_out(corpus, tmp_path):
    out = tmp_path / "out"
    run("analyze", "--source", str(corpus), "--out", str(out))
    run("link", "--source", str(corpus), "--out", str(out))
    link = corpus / "graphify-out"
    assert link.is_symlink() and link.resolve() == (out / "graphify-out").resolve()
    run("link", "--source", str(corpus), "--out", str(out))  # idempotent


def test_default_out_is_curated_basename(corpus, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    run("analyze", "--source", str(corpus))
    assert (tmp_path / "curated" / corpus.name / ".docs-curator").is_dir()
