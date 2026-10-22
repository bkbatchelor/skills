"""Build curated/ from accepted proposals.

Native files Graphify reads are hard-linked (copied if linking fails).
Everything else is written as Markdown with provenance frontmatter. Only
proposals with status `accept` change anything; sources are never touched.
"""

import json
import os
import shutil
from pathlib import Path

from . import SCHEMA_VERSION, die, log, now_iso, read_json, sha256_file, write_json
from . import decisions as dec

OFFICE_REASONS = {"duplicate": "duplicate ({method}) of {keeper}",
                  "revision": "older revision, superseded by {keeper}",
                  "superseded": "marked deprecated or superseded; replaced by {keeper}"}


def effective_keeper(p):
    """final_keeper (user edit), else Claude's suggested winner, else the script's keeper."""
    ids = {m["file"] for m in p["members"]}
    chosen = p.get("final_keeper") or ((p.get("verdict") or {}).get("suggested_winner")) or p.get("keeper")
    if chosen and chosen not in ids:
        die(f"proposal {p['id']}: keeper {chosen} is not one of its members")
    return chosen


def curated_path(rec):
    return f"{rec['source']}/{rec['rel']}" + (".md" if rec["kind"] == "convert" else "")


def yaml_value(v):
    return json.dumps(v, ensure_ascii=False)


def frontmatter(fields):
    lines = ["---"]
    for k, v in fields.items():
        if isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
                continue
            lines.append(f"{k}:")
            for item in v:
                if isinstance(item, dict):
                    first = True
                    for ik, iv in item.items():
                        lines.append(f"  {'- ' if first else '  '}{ik}: {yaml_value(iv)}")
                        first = False
                else:
                    lines.append(f"  - {yaml_value(item)}")
        else:
            lines.append(f"{k}: {yaml_value(v)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def conflict_summary(p):
    v = p.get("verdict") or {}
    if v.get("rationale"):
        text = v["rationale"]
    elif p["method"] == "config_key":
        ev = p["evidence"]
        d = ev["diffs"][0]
        vals = " vs ".join(f"{val}" for k, val in d.items() if k != "key")
        text = f"{ev['diff_count']} config keys differ, e.g. {d['key']}: {vals}"
    else:
        cp = (p["evidence"].get("claim_pairs") or [{}])[0]
        text = f"possible contradiction: \"{cp.get('a', '')[:120]}\" vs \"{cp.get('b', '')[:120]}\""
    winner = v.get("suggested_winner") or p.get("suggested_winner")
    return text + (f" (suggested winner: {winner})" if winner else "")


def plan(doc, files):
    """Work out exclusions and provenance from accepted proposals."""
    excluded, supersedes, dup_of, conflicts, rank = {}, {}, {}, {}, {}
    accepted = [p for p in doc["proposals"] if p["status"] == "accept"]
    for p in accepted:
        if p["kind"] == "conflict":
            continue
        keeper = effective_keeper(p)
        outs = [m["file"] for m in p["members"] if m["file"] != keeper and (keeper or m["role"] == "exclude")]
        for fid in outs:
            reason = OFFICE_REASONS[p["kind"]].format(method=p["method"], keeper=keeper or "no replacement named")
            excluded.setdefault(fid, []).append({"proposal_id": p["id"], "reason": reason, "keeper": keeper})
        if keeper:
            (dup_of if p["kind"] == "duplicate" else supersedes).setdefault(keeper, []).extend(outs)
        if p["kind"] == "revision":
            order = [r["file"] for r in p["evidence"]["ranking"]]
            if keeper in order:
                order.remove(keeper)
                order.insert(0, keeper)
            for i, fid in enumerate(order, 1):
                rank[fid] = i
    for p in accepted:
        if p["kind"] != "conflict" or (p.get("verdict") or {}).get("conflict") is False:
            continue
        a, b = (m["file"] for m in p["members"])
        if a in excluded or b in excluded:
            continue
        for x, y in ((a, b), (b, a)):
            conflicts.setdefault(x, []).append({"path": curated_path(files[y]), "proposal_id": p["id"],
                                                "summary": conflict_summary(p)})
    return excluded, supersedes, dup_of, conflicts, rank


def link_or_copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
        return "hardlink"
    except OSError:
        shutil.copy2(src, dst)
        return "copy"


def unique(dst):
    if not dst.exists():
        return dst
    n = 1
    while dst.with_name(f"{dst.name}.{n}").exists():
        n += 1
    return dst.with_name(f"{dst.name}.{n}")


def run(out_dir, out_arg):
    out = Path(out_dir)
    doc = dec.load(out)
    inv = read_json(out / "inventory.json")
    if not inv:
        die(f"no inventory.json in {out}; run `curate.py analyze` first")
    files = {f["id"]: f for f in inv["files"]}
    for f in files.values():
        if not Path(f["abs"]).is_file() or sha256_file(f["abs"]) != f["sha256"]:
            die(f"{f['id']} changed since analyze; re-run `curate.py analyze`")

    excluded, supersedes, dup_of, conflicts, rank = plan(doc, files)
    unhandled = {u["id"]: u["reason"] for u in inv["unhandled"]}
    curated = out / "curated"
    if curated.is_symlink():
        die(f"{curated} is a symlink; refusing to rebuild it")
    shutil.rmtree(curated, ignore_errors=True)
    curated.mkdir(parents=True)

    entries, quarantine, modes = [], [], {"hardlink": 0, "copy": 0}
    for fid, f in sorted(files.items()):
        base = {"source": f["source"], "path": f["rel"], "sha256": f["sha256"], "format": f["fmt"],
                "commit": f.get("commit")}
        if fid in unhandled:
            entries.append({"kind": "unhandled", **base, "curated_path": None, "reason": unhandled[fid]})
            continue
        if fid in excluded:
            quarantine.append({**{k: base[k] for k in ("source", "path", "sha256", "format")}, "file": fid,
                               "proposal_id": excluded[fid][0]["proposal_id"],
                               "reason": excluded[fid][0]["reason"],
                               "proposals": [e["proposal_id"] for e in excluded[fid]]})
            continue
        prov = {"revision_rank": rank.get(fid), "supersedes": sorted(supersedes.get(fid, [])),
                "duplicates_of_this": sorted(dup_of.get(fid, [])), "conflicts_with": conflicts.get(fid, [])}
        rel_out = curated_path(f)
        dst = unique(curated / rel_out)
        if f["kind"] == "native":
            modes[link_or_copy(f["abs"], dst)] += 1
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            text = (out / "cache" / "text" / f"{f['sha256']}.md").read_text()
            head = {"schema_version": SCHEMA_VERSION, "source": f["source"], "source_location": inv["source_locations"][f["source"]],
                    "commit": f.get("commit"), "path": f["rel"], "sha256": f["sha256"], "format": f["fmt"], **prov}
            dst.write_text(frontmatter(head) + "\n" + text)
        entries.append({"kind": "native" if f["kind"] == "native" else "converted", **base,
                        "source_location": inv["source_locations"][f["source"]],
                        "curated_path": str(dst.relative_to(curated)), **prov})

    write_json(curated / "_manifest.json", {"schema_version": SCHEMA_VERSION, "generated_at": now_iso(),
                                            "entries": entries})
    write_json(out / "quarantine.json", {"schema_version": SCHEMA_VERSION, "generated_at": now_iso(),
                                         "entries": quarantine})
    next_cmd = f"/graphify {Path(out_arg) / 'curated'}"
    log(f"curated {sum(1 for e in entries if e['kind'] != 'unhandled')} files, quarantined {len(quarantine)}, "
        f"unhandled {sum(1 for e in entries if e['kind'] == 'unhandled')}")
    log(f"next: {next_cmd}")
    return {"curated_dir": str(curated), "curated": sum(1 for e in entries if e["kind"] != "unhandled"),
            "native": sum(1 for e in entries if e["kind"] == "native"),
            "converted": sum(1 for e in entries if e["kind"] == "converted"), "quarantined": len(quarantine),
            "unhandled": sum(1 for e in entries if e["kind"] == "unhandled"), "link_modes": modes,
            "accepted": sum(1 for p in doc["proposals"] if p["status"] == "accept"),
            "not_accepted": sum(1 for p in doc["proposals"] if p["status"] != "accept"),
            "manifest": str(curated / "_manifest.json"), "quarantine": str(out / "quarantine.json"), "next": next_cmd}
