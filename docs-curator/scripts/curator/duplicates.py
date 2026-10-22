"""Duplicate clusters: exact bytes, normalized text, near and cross-format.

Tiers run in order and later tiers only see each earlier cluster's keeper:
1. exact sha256 (pre-accepted)
2. normalized text hash, SVG normalized hash (pre-accepted); OCR text (proposed)
3. near-duplicates by MinHash/LSH plus an exact Jaccard check (proposed)

Keeper: highest source priority, then format rank, then newest.
"""

from . import format_rank, IMAGE_FORMATS
from .inventory import CONFIG_FORMATS
from .fingerprint import BANDS, jaccard, lsh_keys
from .revisions import UnionFind, file_date, lineage_stems, parse_name


def keeper_of(members, corpus):
    def key(r):
        ts, _ = file_date(r, corpus.meta(r))
        return (-r["priority"], format_rank(corpus.settings, r["fmt"]), -(ts if ts is not None else r["mtime"]),
                len(r["rel"]), r["rel"], r["source"])
    return min(members, key=key)


def _cluster(method, members, corpus, preaccept, **extra):
    keeper = keeper_of(members, corpus)
    return {"method": method, "members": sorted(members, key=lambda r: r["id"]), "keeper": keeper,
            "preaccept": preaccept, "cross_format": len({m["fmt"] for m in members}) > 1, **extra}


def group_by(files, keyfn):
    out = {}
    for r in files:
        k = keyfn(r)
        if k:
            out.setdefault(k, []).append(r)
    return [g for g in out.values() if len(g) > 1]


def find_duplicates(corpus):
    live = [r for r in corpus.records if r["kind"] != "unhandled"]
    clusters, reps = [], list(live)

    def collapse(groups, method, preaccept):
        nonlocal reps
        drop = set()
        for g in groups:
            c = _cluster(method, g, corpus, preaccept)
            clusters.append(c)
            drop |= {m["id"] for m in g if m["id"] != c["keeper"]["id"]}
        reps = [r for r in reps if r["id"] not in drop]

    collapse(group_by(reps, lambda r: r["sha256"]), "exact", True)
    collapse(group_by([r for r in reps if r["fmt"] not in IMAGE_FORMATS],
                      lambda r: corpus.meta(r).get("norm_hash")), "normalized", True)
    collapse(group_by([r for r in reps if r["fmt"] == "svg"], lambda r: corpus.meta(r).get("svg_hash")),
             "normalized", True)
    collapse(group_by([r for r in reps if r["fmt"] in IMAGE_FORMATS and corpus.meta(r).get("ocr")
                       and corpus.meta(r).get("words", 0) >= 5],
                      lambda r: corpus.meta(r).get("norm_hash")), "ocr", False)
    clusters.extend(near_clusters(
        [r for r in reps if r["fmt"] not in IMAGE_FORMATS | CONFIG_FORMATS and corpus.meta(r).get("sketch")], corpus))
    return clusters


def near_clusters(files, corpus):
    s = corpus.settings
    buckets = {}
    for r in files:
        for key in lsh_keys(corpus.meta(r)["sketch"]):
            buckets.setdefault(key, []).append(r)
    seen, uf, sims = set(), UnionFind(), {}
    for bucket in buckets.values():
        if len(bucket) < 2 or len(bucket) > 200:
            continue
        for i, a in enumerate(bucket):
            for b in bucket[i + 1:]:
                pair = tuple(sorted((a["id"], b["id"])))
                if pair in seen:
                    continue
                seen.add(pair)
                pa, pb = parse_name(a["rel"]), parse_name(b["rel"])
                if pa["vkey"] != pb["vkey"] and lineage_stems(a) & lineage_stems(b):
                    continue                   # different revisions of one document, not copies
                sim = jaccard(corpus.shingles(a), corpus.shingles(b))
                limit = s.cross_sim if a["fmt"] != b["fmt"] else s.near_sim
                if sim >= limit:
                    uf.union(a["id"], b["id"])
                    sims[pair] = sim
    comps = {}
    for r in files:
        if r["id"] in uf.p:
            comps.setdefault(uf.find(r["id"]), []).append(r)
    out = []
    for members in comps.values():
        if len(members) < 2:
            continue
        ids = {m["id"] for m in members}
        low = min(v for (a, b), v in sims.items() if a in ids and b in ids)
        cross = len({m["fmt"] for m in members}) > 1
        out.append(_cluster("cross_format" if cross else "near", members, corpus, False, similarity=round(low, 3)))
    return out
