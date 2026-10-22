"""Revision families, explicit supersession markers and file dates.

Ranking order: explicit markers, then version tokens, then the newest
reliable date (git commit date, metadata or content date), then mtime as a
tie-break only. A low-confidence ranking becomes a review packet.
"""

import difflib
import re
from pathlib import Path

from . import SCHEMA_VERSION, to_ts
from .fingerprint import jaccard

DAY = 86400

TOKENS = [
    ("date", re.compile(r"(?<!\d)(?:19|20)\d{2}[-_.]?(?:0[1-9]|1[0-2])[-_.]?(?:0[1-9]|[12]\d|3[01])(?!\d)")),
    ("date", re.compile(r"(?<!\d)\d{1,2}[-_.]\d{1,2}[-_.](?:\d{4}|\d{2})(?!\d)")),
    ("version", re.compile(r"(?<![a-z0-9])v(?:er(?:sion)?)?[-_ ]?\d+(?:[._]\d+)*(?![a-z0-9])")),
    ("rev", re.compile(r"(?<![a-z0-9])rev(?:ision)?[-_ ]?[a-z0-9]{1,3}(?![a-z0-9])")),
    ("final", re.compile(r"(?<![a-z0-9])final(?![a-z0-9])")),
    ("draft", re.compile(r"(?<![a-z0-9])(?:draft|wip)(?![a-z0-9])")),
    ("copy", re.compile(r"(?<![a-z0-9])copy(?![a-z0-9])|\(\d+\)")),
]


# --- names ---------------------------------------------------------------------

def parse_name(rel):
    """Split a file name into a normalized stem and its revision tokens."""
    name = Path(rel).stem.lower()
    found = []
    for kind, rx in TOKENS:
        for m in rx.finditer(name):
            found.append((kind, m.group(0)))
        name = rx.sub(" ", name)
    stem = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    kinds = {k for k, _ in found}
    nums = ()
    for kind, tok in found:
        if kind == "version":
            nums = tuple(int(n) for n in re.findall(r"\d+", tok))
        elif kind == "rev":
            r = re.sub(r"^rev(?:ision)?[-_ ]?", "", tok)
            nums = (int(r),) if r.isdigit() else (ord(r[0]) - 96 if r[0].isalpha() else 0,)
    cls = 3 if "final" in kinds else 2 if kinds & {"version", "rev"} else 1
    return {"stem": stem, "tokens": found, "kinds": kinds, "vkey": (cls,) + nums,
            "draft": "draft" in kinds, "signal": bool(found)}


def lineage_stems(rec):
    """Name stems a file has had: its current one plus those of earlier git names."""
    stems = {parse_name(rec["rel"])["stem"], *(parse_name(o)["stem"] for o in rec.get("history", []))}
    return stems - {""}


def name_date(rel):
    m = TOKENS[0][1].search(Path(rel).stem.lower())
    if not m:
        return None
    d = re.sub(r"\D", "", m.group(0))
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else None


def file_date(rec, meta):
    """Best reliable date as (timestamp, source), or (None, None)."""
    if rec.get("commit_date"):
        return to_ts(rec["commit_date"]), "git"
    d = meta.get("dates", {})
    for key, label in (("modified", "metadata"), ("content", "content"), ("created", "metadata")):
        if d.get(key) and to_ts(d[key]):
            return to_ts(d[key]), label
    nd = name_date(rec["rel"])
    if nd:
        return to_ts(nd), "name"
    return None, None


# --- explicit markers --------------------------------------------------------------

def resolve_target(target, rec, corpus_records):
    """Find the existing file a marker's `replaced by <x>` points to."""
    if not target:
        return None
    t = target.strip().lstrip("./")
    rel_dir = Path(rec["rel"]).parent
    same = [r for r in corpus_records if r["source"] == rec["source"]]
    for cand in (str(rel_dir / t), t):
        norm = str(Path(cand))
        for r in same:
            if r["rel"] == norm and r["id"] != rec["id"]:
                return r
    base = Path(t).name
    for pool in (same, corpus_records):
        hits = [r for r in pool if Path(r["rel"]).name == base and r["id"] != rec["id"]]
        if len(hits) == 1:
            return hits[0]
    return None


def find_markers(corpus):
    """Return [(file, target-or-None)] for files carrying an explicit marker."""
    out = []
    for rec in corpus.records:
        marker = corpus.meta(rec).get("marker")
        if not marker:
            continue
        target = resolve_target(marker.get("target"), rec, corpus.records)
        if target or marker.get("keyword"):
            out.append((rec, target, marker))
    return out


# --- families ------------------------------------------------------------------------

class UnionFind:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def find_families(survivors, corpus, settings):
    """Group surviving files into revision families and rank each one.

    Returns a list of dicts: members (ranked newest first), confidence,
    reasons, needs_review, via_rename.
    """
    parsed = {r["id"]: parse_name(r["rel"]) for r in survivors}
    groups = {}
    for r in survivors:
        stems = {parsed[r["id"]]["stem"]: False}
        for old in r.get("history", []):
            stems.setdefault(parse_name(old)["stem"], True)
        for stem, via in stems.items():
            if stem:
                groups.setdefault(stem, []).append((r, via))

    uf, renamed = UnionFind(), set()
    for stem, members in groups.items():
        if len(members) < 2:
            continue
        anchors = [(r, via) for r, via in members if via or parsed[r["id"]]["signal"]]
        for a, avia in anchors:
            for b, bvia in members:
                if a["id"] == b["id"]:
                    continue
                rename = avia or bvia
                sim = jaccard(corpus.shingles(a, 3), corpus.shingles(b, 3))
                if sim >= (settings.family_sim / 2 if rename else settings.family_sim):
                    uf.union(a["id"], b["id"])
                    if rename:
                        renamed.update((a["id"], b["id"]))

    comps = {}
    for r in survivors:
        if r["id"] in uf.p:
            comps.setdefault(uf.find(r["id"]), []).append(r)
    families = []
    for members in comps.values():
        if len(members) >= 2:
            families.append(rank_family(members, parsed, corpus, bool(renamed & {m["id"] for m in members})))
    return families


def rank_family(members, parsed, corpus, via_rename):
    rows = []
    for r in members:
        ts, src = file_date(r, corpus.meta(r))
        if ts is None:
            ts, src = r["mtime"], "mtime"
        info = parsed[r["id"]]
        rows.append({"rec": r, "vkey": info["vkey"], "draft": info["draft"], "date": ts, "date_source": src})
    rows.sort(key=lambda x: (x["vkey"], x["date"], x["rec"]["priority"], x["rec"]["id"]), reverse=True)
    top, second = rows[0], rows[1]
    reasons = []

    real = [x for x in rows if x["date_source"] not in ("mtime", "name")]
    date_top = max(real, key=lambda x: x["date"]) if real else None
    both_real = top["date_source"] not in ("mtime",) and second["date_source"] not in ("mtime",)
    if top["vkey"] != second["vkey"]:
        decisive = "version"
    elif abs(top["date"] - second["date"]) >= DAY:
        decisive = "date" if both_real else "mtime"
    else:
        decisive = "none"

    low = decisive in ("mtime", "none")
    if low:
        reasons.append("newest decided only by file modification time" if decisive == "mtime"
                       else "no version or date signal separates the newest members")
    if date_top is not None and date_top is not top and date_top["date"] - top["date"] >= DAY:
        low = True
        reasons.append(f"{date_top['rec']['id']} has a newer date than the highest version")
    if top["draft"]:
        low = True
        reasons.append("the newest member is a draft")
    best_priority = max(x["rec"]["priority"] for x in rows)
    if top["rec"]["priority"] < best_priority:
        low = True
        reasons.append(f"newest member comes from a lower-priority source ({top['rec']['source']})")
    confidence = "low" if low else ("high" if decisive == "version" else "medium")
    return {"members": rows, "confidence": confidence, "reasons": reasons, "decisive": decisive,
            "via_rename": via_rename, "needs_review": low}


def signals(row):
    return {"version_key": list(row["vkey"]), "draft": row["draft"], "date": row["date"],
            "date_source": row["date_source"]}


def packet_for_revision(pid, proposal, family, corpus, settings):
    rows = family["members"]
    top, second = rows[0]["rec"], rows[1]["rec"]
    diff = list(difflib.unified_diff(corpus.text(second).splitlines(), corpus.text(top).splitlines(),
                                     second["id"], top["id"], n=1, lineterm=""))
    return {
        "schema_version": SCHEMA_VERSION, "proposal_id": pid, "kind": "revision",
        "question": "Which of these files is the current revision? Say whether the script's keeper is right, "
                    "and name the winner if not.",
        "script_keeper": proposal["keeper"], "confidence": family["confidence"], "reasons": family["reasons"],
        "files": [{"file": x["rec"]["id"], "source": x["rec"]["source"], "priority": x["rec"]["priority"],
                   "path": x["rec"]["rel"], "signals": signals(x),
                   "commit_date": x["rec"].get("commit_date"),
                   "excerpt": corpus.text(x["rec"])[:settings.excerpt_chars]} for x in rows],
        "diff_newest_vs_next": diff[:80],
    }
