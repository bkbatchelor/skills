#!/usr/bin/env python3
"""Curate document sources before they go into a knowledge graph.

Finds duplicates (including the same content in different formats), outdated
or superseded revisions and contradictions across one or more local folders
and git repos, writes proposals for you to review, then builds a clean
curated/ tree of Markdown conversions and hard-linked native files.
Sources are never modified. Standard library only; poppler, LibreOffice and
tesseract are optional external tools.

    curate.py analyze [PATH|URL ...] [--sources sources.toml]
    curate.py record VERDICTS
    curate.py apply
    curate.py status

Prints one JSON summary line on stdout. Progress and errors go to stderr.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from curator import SCHEMA_VERSION, Settings, die, load_config, log, read_json, write_json  # noqa: E402
from curator import apply as apply_mod  # noqa: E402
from curator import decisions as dec  # noqa: E402
from curator import inventory, report, sources as src  # noqa: E402
from curator.extract import Corpus, extract  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUT = "docs-curator-out"


def emit(data):
    print(json.dumps({"schema_version": SCHEMA_VERSION, **data}, ensure_ascii=False))


def unhandled_reason(rec):
    if rec["lfs"]:
        return "git-lfs pointer file; the real content was not fetched"
    return f"unsupported format .{rec['fmt']}" if rec["fmt"] else "file has no extension"


# --- analyze --------------------------------------------------------------------------

def declared_sources(a):
    if a.sources:
        return src.load_toml(a.sources)
    if a.inputs:
        return src.from_args(a.inputs)
    if Path("sources.toml").is_file():
        return src.load_toml("sources.toml")
    die("no sources: pass paths or URLs, --sources sources.toml, or run in a folder with sources.toml")


def cmd_analyze(a):
    settings = Settings(load_config())
    out = Path(a.out).resolve()
    sources = declared_sources(a)
    if a.dry_run:
        plan = []
        for s in sources:
            n = None if s.url else sum(1 for _ in Path(s.path).rglob("*") if _.is_file()) if Path(s.path).is_dir() else 0
            plan.append({**s.public(), "files": n, "would_clone": bool(s.url)})
        emit({"dry_run": True, "out_dir": str(out), "sources": plan})
        return
    out.mkdir(parents=True, exist_ok=True)
    src.prepare(sources, out)
    records = inventory.scan(sources, out)
    if not records:
        die("no files found in the sources")

    cache = out / "cache"
    metas, hits, misses, notes = {}, 0, 0, []
    todo = [r for r in records if r["kind"] != "unhandled"]
    for i, rec in enumerate(todo, 1):
        meta, hit = extract(rec, settings, cache, force=a.force)
        hits, misses = hits + hit, misses + (not hit)
        metas[rec["id"]] = meta
        if meta.get("error"):
            rec["kind"], rec["extract_error"] = "unhandled", meta["error"]
        for n in meta.get("notes", []):
            notes.append({"id": rec["id"], "note": n})
        if meta.get("partial_parse"):
            notes.append({"id": rec["id"], "note": "partial_parse: YAML or config only partly flattened"})
        if i % 200 == 0:
            log(f"extracted {i}/{len(todo)}")

    unhandled = [{"id": r["id"], "reason": unhandled_reason(r) if not r.get("extract_error")
                  else f"extraction failed: {r['extract_error']}"} for r in records if r["kind"] == "unhandled"]
    corpus = Corpus(records, metas, cache, settings)
    proposals, packets, unreviewed = dec.build(corpus, settings)
    previous = read_json(out / "decisions.json")
    kept, dropped = dec.merge_previous(proposals, previous)

    stats = {"files": len(records), "unhandled": len(unhandled), "curated_candidates": len(records) - len(unhandled)}
    write_json(out / "inventory.json", {
        "schema_version": SCHEMA_VERSION, "sources": [s.public() for s in sources],
        "source_locations": {s.name: s.location for s in sources}, "stats": stats,
        "files": records, "unhandled": unhandled, "notes": notes})
    dec.write_packets(out, packets)
    doc = dec.save(out, sources, proposals, unreviewed, dropped, settings)
    inv = read_json(out / "inventory.json")
    md, html_path = report.write(out, doc, inv)

    by = Counter(f"{p['kind']}:{p['method']}" for p in proposals)
    emit({"out_dir": str(out), "decisions": str(out / "decisions.json"), "report": md, "report_html": html_path,
          "sources": [{"name": s.name, "priority": s.priority, "commit": s.commit,
                       "files": sum(1 for r in records if r["source"] == s.name)} for s in sources],
          "files": len(records), "unhandled": len(unhandled), "proposals": dict(sorted(by.items())),
          "preaccepted": sum(p["preaccepted"] for p in proposals),
          "needs_decision": sum(p["status"] == "proposed" for p in proposals),
          "packets": len(packets), "unreviewed": len(unreviewed), "kept_statuses": kept, "dropped": len(dropped),
          "cache_hits": hits, "cache_misses": misses,
          "warnings": [n["id"] + ": " + n["note"] for n in notes if n["note"].startswith("partial_parse")]})


# --- record / apply / status ----------------------------------------------------------------

def cmd_record(a):
    recorded, errors = dec.record(Path(a.out), a.verdicts)
    emit({"recorded": len(recorded), "proposal_ids": recorded, "errors": errors,
          "decisions": str(Path(a.out) / "decisions.json")})
    if errors and not recorded:
        sys.exit(1)


def cmd_apply(a):
    emit(apply_mod.run(Path(a.out).resolve(), a.out))


def cmd_status(a):
    out = Path(a.out)
    doc = dec.load(out)
    props = doc["proposals"]
    packets = [p for p in props if p.get("packet")]
    pending = [p["id"] for p in packets if not p.get("verdict")]
    emit({"out_dir": str(out.resolve()),
          "proposals": len(props),
          "by_status": dict(Counter(p["status"] for p in props)),
          "by_kind": dict(Counter(f"{p['kind']}:{p['method']}" for p in props)),
          "packets": len(packets), "packets_without_verdict": pending, "unreviewed": doc["unreviewed"],
          "curated": (out / "curated" / "_manifest.json").is_file()})


# --- cli --------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Each subcommand prints one JSON summary line on stdout.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def with_out(p):
        p.add_argument("--out", default=DEFAULT_OUT, help=f"output folder (default ./{DEFAULT_OUT})")
        return p

    p = with_out(sub.add_parser("analyze", help="scan sources and write decisions.json, packets and the report"))
    p.add_argument("inputs", nargs="*", help="folders, git repos or git URLs (name from basename, priority 0)")
    p.add_argument("--sources", metavar="TOML", help="sources.toml with [[source]] entries")
    p.add_argument("--force", action="store_true", help="ignore the extraction cache")
    p.add_argument("--dry-run", action="store_true", help="list sources and file counts; clone and write nothing")
    p.set_defaults(fn=cmd_analyze)

    p = with_out(sub.add_parser("record", help="merge Claude's verdicts into decisions.json (never changes status)"))
    p.add_argument("verdicts", help="a verdicts JSON file, or a folder of them")
    p.set_defaults(fn=cmd_record)

    p = with_out(sub.add_parser("apply", help="build curated/ from the accepted proposals"))
    p.set_defaults(fn=cmd_apply)

    p = with_out(sub.add_parser("status", help="counts of proposals, packets and verdicts"))
    p.set_defaults(fn=cmd_status)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
