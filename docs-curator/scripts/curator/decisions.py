"""Proposals: build them from the analysis, keep the user's earlier
statuses across re-runs, and merge Claude's verdicts without touching status.
"""

import hashlib
from pathlib import Path

from . import SCHEMA_VERSION, die, log, now_iso, read_json, write_json
from .conflicts import config_conflicts, packet_for_prose, prose_conflicts
from .duplicates import find_duplicates
from .revisions import find_families, find_markers, packet_for_revision, signals

STATUSES = ("proposed", "accept", "reject")
KEEP_FROM_PREVIOUS = ("status", "verdict", "final_keeper", "note")


def member(rec, role):
    return {"file": rec["id"], "source": rec["source"], "path": rec["rel"], "sha256": rec["sha256"],
            "format": rec["fmt"], "role": role}


def proposal_id(kind, method, members):
    h = hashlib.sha256((f"{kind}:{method}\n" + "\n".join(sorted(m["sha256"] for m in members))).encode())
    return f"{kind}-{h.hexdigest()[:12]}"


def make(kind, method, members, preaccept=False, **fields):
    pid = proposal_id(kind, method, members)
    p = {"id": pid, "kind": kind, "method": method, "status": "accept" if preaccept else "proposed",
         "preaccepted": preaccept, "keeper": None, "suggested_winner": None, "members": members,
         "evidence": {}, "needs_review": False, "review_reason": None, "packet": None, "verdict": None}
    p.update(fields)
    return p


# --- build ---------------------------------------------------------------------------

def build(corpus, settings):
    """Run every detector. Returns (proposals, packets-by-id, unreviewed ids)."""
    records = corpus.records
    proposals, review = [], []              # review: (order, proposal, packet)

    marked_ids = set()
    for rec, target, marker in find_markers(corpus):
        marked_ids.add(rec["id"])
        members = [member(rec, "exclude")] + ([member(target, "keeper")] if target else [])
        proposals.append(make("superseded", "marker" if target else "marker_no_target", members, preaccept=bool(target),
                              keeper=target["id"] if target else None,
                              evidence={"marker_target": marker.get("target"), "resolved": target["id"] if target else None},
                              needs_review=target is None,
                              review_reason=None if target else "marker names no existing replacement file"))

    dup_out = set()
    for c in find_duplicates(corpus):
        keeper = c["keeper"]
        members = [member(m, "keeper" if m["id"] == keeper["id"] else "exclude") for m in c["members"]]
        dup_out |= {m["id"] for m in c["members"] if m["id"] != keeper["id"]}
        proposals.append(make("duplicate", c["method"], members, preaccept=c["preaccept"], keeper=keeper["id"],
                              evidence={"similarity": c.get("similarity"), "cross_format": c["cross_format"],
                                        "formats": sorted({m["fmt"] for m in c["members"]})}))

    survivors = [r for r in records if r["kind"] != "unhandled" and r["id"] not in dup_out and r["id"] not in marked_ids]

    rev_out = set()
    for fam in find_families(survivors, corpus, settings):
        rows = fam["members"]
        keeper = rows[0]["rec"]
        members = [member(x["rec"], "keeper" if x is rows[0] else "exclude") for x in rows]
        rev_out |= {x["rec"]["id"] for x in rows[1:]}
        p = make("revision", "rename_chain" if fam["via_rename"] else "version_family", members, keeper=keeper["id"],
                 evidence={"confidence": fam["confidence"], "decided_by": fam["decisive"], "reasons": fam["reasons"],
                           "ranking": [{"rank": i + 1, "file": x["rec"]["id"], **signals(x)} for i, x in enumerate(rows)]},
                 needs_review=fam["needs_review"], review_reason="; ".join(fam["reasons"]) or None)
        proposals.append(p)
        if fam["needs_review"]:
            review.append((0, p["id"], p, packet_for_revision(p["id"], p, fam, corpus, settings)))

    alive = [r for r in survivors if r["id"] not in rev_out]
    for c in config_conflicts(alive, corpus, settings):
        a, b = c["members"]
        proposals.append(make("conflict", c["method"], [member(a, "side"), member(b, "side")],
                              suggested_winner=c["suggested_winner"], evidence=c["evidence"]))
    for c in prose_conflicts(alive, corpus, settings):
        a, b = c["members"]
        p = make("conflict", "prose", [member(a, "side"), member(b, "side")], suggested_winner=c["suggested_winner"],
                 evidence=c["evidence"], needs_review=True, review_reason="prose claims need a judgement")
        proposals.append(p)
        review.append((1, -c["score"], p, packet_for_prose(p["id"], p, a, b, corpus, settings)))

    review.sort(key=lambda x: (x[0], x[1]))
    packets, unreviewed = {}, []
    for _, _, p, packet in review:
        if len(packets) < settings.packet_cap:
            packets[p["id"]] = packet
            p["packet"] = f"packets/{p['id']}.json"
        else:
            unreviewed.append(p["id"])
    proposals.sort(key=lambda p: p["id"])
    return proposals, packets, unreviewed


# --- previous decisions ---------------------------------------------------------------------

def merge_previous(proposals, previous):
    """Keep status, verdict, final_keeper and note from an earlier run."""
    old = {p["id"]: p for p in (previous or {}).get("proposals", [])}
    kept = 0
    for p in proposals:
        prev = old.get(p["id"])
        if prev:
            for key in KEEP_FROM_PREVIOUS:
                if key in prev and prev[key] is not None:
                    p[key] = prev[key]
            kept += 1
    dropped = sorted(set(old) - {p["id"] for p in proposals})
    return kept, dropped


def write_packets(out_dir, packets):
    pdir = Path(out_dir) / "packets"
    pdir.mkdir(parents=True, exist_ok=True)
    for stale in pdir.glob("*.json"):
        if stale.stem not in packets:
            stale.unlink()
    for pid, packet in packets.items():
        write_json(pdir / f"{pid}.json", packet)


def save(out_dir, sources, proposals, unreviewed, dropped, settings):
    doc = {"schema_version": SCHEMA_VERSION, "generated_at": now_iso(), "sources": [s.public() for s in sources],
           "settings": settings.as_dict(), "proposals": proposals, "unreviewed": unreviewed, "dropped": dropped}
    write_json(Path(out_dir) / "decisions.json", doc)
    return doc


def load(out_dir):
    doc = read_json(Path(out_dir) / "decisions.json")
    if not doc:
        die(f"no decisions.json in {out_dir}; run `curate.py analyze` first")
    return doc


# --- record ------------------------------------------------------------------------------------

def read_verdict_files(path):
    path = Path(path)
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    if not files:
        die(f"no verdict files at {path}")
    verdicts = []
    for f in files:
        try:
            data = read_json(f)
        except ValueError as e:
            die(f"{f}: not valid JSON ({e})")
        if isinstance(data, dict) and "verdicts" in data:
            data = data["verdicts"]
        verdicts.extend(data if isinstance(data, list) else [data])
    return files, verdicts


def record(out_dir, path):
    """Attach verdicts to proposals. Never changes `status`."""
    doc = load(out_dir)
    by_id = {p["id"]: p for p in doc["proposals"]}
    files, verdicts = read_verdict_files(path)
    recorded, errors = [], []
    for v in verdicts:
        pid = v.get("proposal_id") if isinstance(v, dict) else None
        p = by_id.get(pid)
        if not p:
            errors.append({"proposal_id": pid, "error": "unknown proposal id"})
            continue
        winner = v.get("suggested_winner")
        if winner and winner not in {m["file"] for m in p["members"]}:
            errors.append({"proposal_id": pid, "error": f"suggested_winner {winner} is not a member"})
            continue
        if p["kind"] == "conflict" and v.get("conflict") is None:
            errors.append({"proposal_id": pid, "error": "conflict verdicts need conflict: true or false"})
            continue
        p["verdict"] = {"suggested_winner": winner, "conflict": v.get("conflict"), "rationale": v.get("rationale", ""),
                        "confidence": v.get("confidence"), "claims": v.get("claims", []), "recorded_at": now_iso()}
        recorded.append(pid)
    vdir = Path(out_dir) / "verdicts"
    vdir.mkdir(exist_ok=True)
    for f in files:
        (vdir / f.name).write_text(f.read_text())
    write_json(Path(out_dir) / "decisions.json", doc)
    log(f"recorded {len(recorded)} verdicts, {len(errors)} errors")
    return recorded, errors
