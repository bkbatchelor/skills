"""Unit tests for the rules settled in the requirements and the plan."""
import json
import zipfile
from pathlib import Path

import pytest

import curate
from curate import (
    analyze_chain, cluster_id, decide, describe, dice, extract_text, find_collisions, find_subsumed,
    id_sites, load_config, load_overrides, normalize, parse_name, shingle_set, similarity,
    split_front_matter, text_signals,
)

CFG = dict(curate.DEFAULTS)


# ---- filename markers ---------------------------------------------------------


@pytest.mark.parametrize("stem,expect_stem", [
    ("report_v2", "report"), ("v2_report", "report"), ("updated-report", "report"),
    ("report-final", "report"), ("final_report", "report"), ("copy_of_report", "report"),
    ("report_copy", "report"), ("Report Rev 3", "report"), ("budget_2024", "budget-2024"),
    ("design_spec_v2.1", "design-spec"),
])
def test_markers_are_read_at_both_ends(stem, expect_stem):
    assert parse_name(stem)["stem"] == expect_stem


def test_marker_tiers():
    assert parse_name("a_v3")["version"] == (3,)
    assert parse_name("a_v2.1")["version"] == (2, 1)
    assert parse_name("a_updated")["strict"] == 1
    assert parse_name("a_revised")["strict"] == 1
    assert parse_name("a_final")["ambiguous"] == 1 and parse_name("a_final")["strict"] == 0
    assert parse_name("a_draft")["ambiguous"] == -1
    assert parse_name("a")["markers"] == 0


def test_copy_alone_in_a_name_is_not_a_marker():
    assert parse_name("copy")["stem"] == "copy"


# ---- text normalisation -------------------------------------------------------


def test_normalize_strips_slide_markers_and_deck_notes():
    text = "<!-- Slide number: 1 -->\n# Title\n\nBody\n\n### Notes:\nsecret notes\n\n<!-- Slide number: 2 -->\n# Two"
    toks = normalize(text, "pptx")
    assert toks == ["title", "body", "two"]
    assert "secret" in normalize(text, "pdf")  # notes only stripped for decks


def test_normalize_ignores_case_formatting_and_page_lines():
    assert normalize("**Hello**,  World!\nPage 3 of 9\n", "pdf") == ["hello", "world"]


# ---- extraction ---------------------------------------------------------------


def test_md_and_txt_are_read_as_utf8(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("café — ünïcode ✓\n", encoding="utf-8")
    assert extract_text(f, "md") == "café — ünïcode ✓\n"


def test_charset_guessing_is_fallback_only(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes("caf\xe9".encode("cp1252"))
    assert extract_text(f, "txt") == "café"


def test_broken_containers_are_rejected(tmp_path):
    f = tmp_path / "a.docx"
    f.write_bytes(b"plain text pretending to be a docx")
    with pytest.raises(ValueError):
        extract_text(f, "docx")
    g = tmp_path / "a.pdf"
    g.write_bytes(b"not a pdf")
    with pytest.raises(ValueError):
        extract_text(g, "pdf")


# ---- descriptions and front matter ---------------------------------------------


def test_description_prefers_first_h1_or_h2():
    assert describe("intro line\n\n## Second heading\n\n# Later", "stem") == "Second heading"


def test_description_falls_back_to_first_line_then_stem():
    assert describe("\n\nJust a line of text\nmore", "stem") == "Just a line of text"
    assert describe("   \n\n", "report_x") == "report_x"
    assert describe("<!-- Slide number: 1 -->\n", "deck") == "deck"


def test_description_is_truncated():
    d = describe("# " + "word " * 100, "stem")
    assert len(d) <= 160 and d.endswith("…")


def test_front_matter_parse_and_failure():
    meta, body, ok = split_front_matter("---\ntitle: A\n---\nbody\n")
    assert meta == {"title": "A"} and body == "body\n" and ok
    meta, body, ok = split_front_matter("---\ntitle: [unclosed\n---\nbody\n")
    assert meta is None and not ok and body.startswith("---")
    assert split_front_matter("no front matter") == (None, "no front matter", True)


def test_make_doc_nests_source_front_matter_and_warns_on_bad(tmp_path):
    warnings = []
    good = curate.make_doc("a.md", "md", "abc", "unique", "---\nowner: x\n---\n# Title\n", warnings)
    meta, _, _ = split_front_matter(good)
    assert meta["source_front_matter"] == {"owner": "x"} and meta["description"] == "Title" and not warnings
    bad = curate.make_doc("b.md", "md", "abc", "unique", "---\nx: [oops\n---\ntext\n", warnings)
    assert warnings and "x: [oops" in bad.split("---\n", 2)[-1]


# ---- similarity ----------------------------------------------------------------


def test_similarity_exact_and_dice_fallback():
    a = ("alpha beta gamma delta " * 10).split()
    assert similarity(a, a, 50000) == 1.0
    assert similarity(a, a, 5) == 1.0  # over the token cap -> Dice
    b = a[:-4]
    assert similarity(a, b, 5) <= similarity(a, b, 50000) + 1e-9  # fallback never reads higher
    assert dice([], []) == 0.0


def test_subsumed_needs_containment_and_length_gap():
    big = ("w%d" % i for i in range(200))
    big = list(big)
    small = big[40:140]
    docs = {"big": (big, shingle_set(big)), "small": (small, shingle_set(small))}
    found = find_subsumed(docs, 0.95, 0.20)
    assert "small" in found and found["small"][0][0] == "big"
    near = big[:190]  # only 5% shorter: not subsumed
    docs = {"big": (big, shingle_set(big)), "near": (near, shingle_set(near))}
    assert find_subsumed(docs, 0.95, 0.20) == {}


def test_cluster_id_is_order_independent():
    assert cluster_id(["b", "a"]) == cluster_id(["a", "b"])
    assert len(cluster_id(["a"])) == 16


# ---- revision chains --------------------------------------------------------------


def member(name, text_version=None, text_date=None, core=None, mtime=0.0):
    return {"name": parse_name(name), "text_version": text_version, "text_date": text_date, "core_modified": core, "mtime": mtime}


def test_text_signals():
    s = text_signals("# T\n\nVersion: 2.1\nLast updated: 2024-03-05\n")
    assert s == {"text_version": [2, 1], "text_date": "2024-03-05"}
    assert text_signals("nothing here") == {"text_version": None, "text_date": None}


def test_two_agreeing_signals_are_deterministic():
    info = {"r.md": member("r", [1], "2024-01-01", mtime=1), "r_v2.md": member("r_v2", [2], "2024-02-01", mtime=2)}
    ch = analyze_chain(list(info), info)
    assert ch["order"] == ["r.md", "r_v2.md"] and ch["deterministic"]


def test_contradicting_signal_blocks_determinism():
    info = {"r.md": member("r", [2], "2024-03-01", mtime=1), "r_v2.md": member("r_v2", [1], "2024-02-01", mtime=2)}
    ch = analyze_chain(list(info), info)
    assert ch["contradicting"] and not ch["deterministic"]


def test_mtime_never_blocks_and_never_counts():
    info = {"r.md": member("r", [1], "2024-01-01", mtime=9), "r_v2.md": member("r_v2", [2], "2024-02-01", mtime=1)}
    ch = analyze_chain(list(info), info)
    assert ch["deterministic"] and not ch["mtime_agrees"]
    only_mtime = {"r.md": member("r", mtime=1), "r_updated.md": member("r_final", mtime=2)}
    assert not analyze_chain(list(only_mtime), only_mtime)["deterministic"]


def test_ambiguous_marker_counts_only_when_text_agrees():
    base = {"r.md": member("r", [1], "2024-01-01"), "r_final.md": member("r_final", [2], "2024-02-01")}
    ch = analyze_chain(list(base), base)
    assert "ambiguous_marker" in ch["agreeing"] and ch["deterministic"]
    lone = {"r.md": member("r"), "r_final.md": member("r_final")}
    ch = analyze_chain(list(lone), lone)
    assert ch["agreeing"] == [] and not ch["deterministic"]
    disagree = {"r.md": member("r", [2]), "r_final.md": member("r_final", [1])}
    ch = analyze_chain(list(disagree), disagree)
    assert ch["ambiguous_ignored"] and "ambiguous_marker" not in ch["agreeing"]


def test_draft_is_older_than_unmarked():
    info = {"r.md": member("r", [2], "2024-02-01"), "r_draft.md": member("r_draft", [1], "2024-01-01")}
    assert analyze_chain(list(info), info)["order"] == ["r_draft.md", "r.md"]


# ---- identifier collisions ----------------------------------------------------------


def test_identifier_sites_are_narrow():
    text = "# PRJ-1 Login fix\n\nSee also ABC-77 in the text.\n\n| ID | Title |\n|---|---|\n| PRJ-2 | Rotate keys |\n"
    sites = id_sites("PRJ-9_banner.md", text, CFG)
    kinds = {(i, s) for i, s, _ in sites}
    assert ("PRJ-9", "filename") in kinds and ("PRJ-1", "heading") in kinds and ("PRJ-2", "index_table") in kinds
    assert not any(i == "ABC-77" for i, _, _ in sites)  # prose mentions are not definitions


def test_table_needs_an_identifier_header():
    text = "| Name | Title |\n|---|---|\n| PRJ-2 | Rotate keys |\n"
    assert id_sites("x.md", text, CFG) == []


def test_collision_needs_disjoint_titles_in_different_files():
    same = {"a.md": [("PRJ-1", "heading", "Rotate database credentials")], "b.md": [("PRJ-1", "heading", "Rotate database credentials v2")]}
    assert find_collisions(same) == []
    diff = {"a.md": [("PRJ-1", "heading", "Rotate database credentials")], "b.md": [("PRJ-1", "heading", "Homepage banner redesign")]}
    assert [c["id"] for c in find_collisions(diff)] == ["PRJ-1"]
    one_file = {"a.md": [("PRJ-1", "heading", "Rotate"), ("PRJ-1", "filename", "Banner")]}
    assert find_collisions(one_file) == []


# ---- decide(): precedence and fail-open behaviour ------------------------------------------


def F(path, fmt="md", sha=None, status="ok"):
    return {"path": path, "format": fmt, "ext": "." + fmt, "sha256": sha or path, "status": status, "error": None}


def analysis(files, **kw):
    reps = {f["sha256"]: f["path"] for f in files if f["status"] in ("ok", "text_free")}
    base = {"files": files, "reps": reps, "edges": [], "dup_groups": [], "subsumed": [], "chains": []}
    base.update(kw)
    return base


def test_exact_duplicate_copies_point_at_the_keeper():
    files = [F("a.md", sha="s"), F("b.md", sha="s")]
    an = analysis(files)
    an["reps"] = {"s": "a.md"}
    dec, _, _ = decide(an, CFG, {}, [])
    assert dec["b.md"]["reason"] == "exact_duplicate" and dec["b.md"]["kept_instead"] == "a.md"
    assert dec["a.md"]["reason"] == "unique"


def dup_analysis():
    files = [F("a.md"), F("b.md")]
    return analysis(files, edges=[{"a": "a.md", "b": "b.md", "sim": 0.95, "kind": "near"}],
                    dup_groups=[{"keeper": "a.md", "members": ["a.md", "b.md"]}])


def test_near_duplicate_is_a_config_switch():
    dec, _, _ = decide(dup_analysis(), CFG, {}, [])
    assert (dec["b.md"]["action"], dec["b.md"]["reason"]) == ("include", "near_duplicate_flag")
    dec, _, _ = decide(dup_analysis(), dict(CFG, near_duplicate_action="exclude"), {}, [])
    assert (dec["b.md"]["action"], dec["b.md"]["reason"]) == ("exclude", "near_duplicate")


def test_cross_format_is_excluded_regardless_of_near_action():
    files = [F("a.pptx", "pptx"), F("a.pdf", "pdf")]
    an = analysis(files, edges=[{"a": "a.pdf", "b": "a.pptx", "sim": 0.97, "kind": "cross"}],
                  dup_groups=[{"keeper": "a.pptx", "members": ["a.pdf", "a.pptx"]}])
    dec, _, _ = decide(an, CFG, {}, [])
    assert dec["a.pdf"]["reason"] == "format_duplicate" and dec["a.pptx"]["action"] == "convert"


def chain_analysis(deterministic):
    files = [F("r.md"), F("r_v2.md")]
    ch = {"order": ["r.md", "r_v2.md"], "members": ["r.md", "r_v2.md"], "agreeing": ["a", "b"] if deterministic else [],
          "contradicting": [], "deterministic": deterministic, "mtime_agrees": True}
    return analysis(files, chains=[ch])


def rev(conf, by="r_v2.md"):
    return {"cluster_id": "c", "revisions": [{"superseded": "r.md", "superseded_by": by, "confidence": conf, "unique_content": []}], "conflicts": []}


def test_superseded_beats_near_duplicate_flag():
    an = chain_analysis(True)
    an["edges"] = [{"a": "r.md", "b": "r_v2.md", "sim": 0.95, "kind": "near"}]
    an["dup_groups"] = [{"keeper": "r.md", "members": ["r.md", "r_v2.md"]}]
    dec, _, _ = decide(an, CFG, {}, [])
    assert dec["r.md"]["reason"] == "superseded"
    assert dec["r_v2.md"]["reason"] == "unique"  # the flag would have landed here otherwise


def test_near_exclude_beats_superseded():
    an = chain_analysis(True)
    an["edges"] = [{"a": "r.md", "b": "r_v2.md", "sim": 0.95, "kind": "near"}]
    an["dup_groups"] = [{"keeper": "r.md", "members": ["r.md", "r_v2.md"]}]
    dec, _, _ = decide(an, dict(CFG, near_duplicate_action="exclude"), {}, [])
    assert dec["r_v2.md"]["reason"] == "near_duplicate"


def test_verdict_confidence_threshold():
    dec, _, _ = decide(chain_analysis(False), CFG, {}, [rev(0.80)])
    assert dec["r.md"]["reason"] == "superseded"
    dec, _, _ = decide(chain_analysis(False), CFG, {}, [rev(0.60)])
    assert (dec["r.md"]["action"], dec["r.md"]["reason"]) == ("include", "low_confidence_keep")
    dec, _, _ = decide(chain_analysis(False), CFG, {}, [])  # missing verdict means keep
    assert (dec["r.md"]["action"], dec["r.md"]["reason"]) == ("include", "low_confidence_keep")
    dec, _, _ = decide(chain_analysis(False), dict(CFG, low_confidence_threshold=0.5), {}, [rev(0.60)])
    assert dec["r.md"]["reason"] == "superseded"


def test_deterministic_chain_needs_no_verdict_and_wins_over_a_contradicting_one():
    dec, _, _ = decide(chain_analysis(True), CFG, {}, [])
    assert dec["r.md"]["reason"] == "superseded" and dec["r.md"]["kept_instead"] == "r_v2.md"
    dec, warns, _ = decide(chain_analysis(True), CFG, {}, [rev(0.99, by="elsewhere.md")])
    assert dec["r.md"]["kept_instead"] == "r_v2.md"


def test_verdict_naming_unknown_paths_is_ignored():
    dec, warns, _ = decide(chain_analysis(False), CFG, {}, [rev(0.99, by="ghost.md")])
    assert warns and dec["r.md"]["reason"] == "low_confidence_keep"


def test_subsumed_is_a_flag_and_comes_last():
    files = [F("big.md"), F("small.md")]
    an = analysis(files, subsumed=[{"path": "small.md", "containers": [{"path": "big.md", "containment": 0.99}]}])
    dec, _, _ = decide(an, CFG, {}, [])
    assert (dec["small.md"]["action"], dec["small.md"]["reason"], dec["small.md"]["kept_instead"]) == ("include", "subsumed_flag", "big.md")


def test_subsumed_container_must_be_kept():
    files = [F("big.md", sha="s"), F("big_copy.md", sha="s"), F("small.md")]
    an = analysis(files, subsumed=[{"path": "small.md", "containers": [{"path": "big_copy.md", "containment": 0.99}]}])
    an["reps"] = {"s": "big.md", "small.md": "small.md"}
    dec, _, _ = decide(an, CFG, {}, [])
    assert dec["small.md"]["reason"] == "unique"  # the container was an excluded exact copy


def test_overrides_win_but_cannot_rescue_unreadable():
    files = [F("a.md", sha="s"), F("b.md", sha="s"), F("c.docx", "docx", status="unreadable"), F("d.md")]
    an = analysis(files)
    an["reps"] = {"s": "a.md", "d.md": "d.md"}
    dec, warns, _ = decide(an, CFG, {"b.md": {"action": "include", "note": ""}, "d.md": {"action": "exclude", "note": "n"}, "c.docx": {"action": "include", "note": ""}}, [])
    assert dec["b.md"]["reason"] == "override_include" and dec["b.md"]["action"] == "include"
    assert dec["d.md"]["reason"] == "override_exclude" and dec["d.md"]["action"] == "exclude"
    assert dec["c.docx"]["action"] == "unreadable" and warns


def test_kept_decks_convert_and_text_free_is_flagged():
    files = [F("d.pptx", "pptx"), F("blank.pdf", "pdf", status="text_free")]
    dec, _, _ = decide(analysis(files), CFG, {}, [])
    assert dec["d.pptx"]["action"] == "convert"
    assert dec["blank.pdf"]["evidence"] == {"text_free": True} and dec["blank.pdf"]["action"] == "include"


# ---- config and overrides ----------------------------------------------------------------------


def test_config_defaults_and_validation(tmp_path):
    assert load_config(tmp_path)["near_duplicate_action"] == "flag"
    (tmp_path / "config.yaml").write_text("near_duplicate_action: exclude\nmax_llm_clusters_per_run: 3\n")
    cfg = load_config(tmp_path)
    assert cfg["near_duplicate_action"] == "exclude" and cfg["max_llm_clusters_per_run"] == 3
    (tmp_path / "config.yaml").write_text("near_duplicate_action: maybe\n")
    with pytest.raises(SystemExit):
        load_config(tmp_path)
    (tmp_path / "config.yaml").write_text("not_a_setting: 1\n")
    with pytest.raises(SystemExit):
        load_config(tmp_path)


def test_overrides_file(tmp_path):
    assert load_overrides(tmp_path) == {}
    (tmp_path / "overrides.yaml").write_text("- {path: a.md, action: exclude, note: why}\n")
    assert load_overrides(tmp_path)["a.md"] == {"action": "exclude", "note": "why"}
    (tmp_path / "overrides.yaml").write_text("- {path: a.md, action: delete}\n")
    with pytest.raises(SystemExit):
        load_overrides(tmp_path)


def test_malformed_verdicts_are_skipped(tmp_path):
    v = tmp_path / ".docs-curator" / "work" / "verdicts"
    v.mkdir(parents=True)
    (v / "bad.json").write_text("{not json")
    (v / "ok.json").write_text(json.dumps({"cluster_id": "ok", "reviewed": True}))
    verdicts, warns = curate.load_verdicts(tmp_path / ".docs-curator")
    assert [x["cluster_id"] for x in verdicts] == ["ok"] and len(warns) == 1
