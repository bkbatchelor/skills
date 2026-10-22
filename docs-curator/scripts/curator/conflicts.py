"""Contradiction candidates.

Config files (json, yaml, toml, ini, properties) are compared key by key,
but only inside one logical file (same path once environment tokens are
removed) and one environment scope. Prose is grouped into topic clusters
and turned into candidate claim pairs for Claude to judge from a packet.
"""

import math
import re
from collections import Counter
from itertools import combinations

from . import SCHEMA_VERSION
from .inventory import CONFIG_FORMATS
from .revisions import file_date

ALIASES = {"development": "dev", "production": "prod", "stage": "staging"}
REGION = re.compile(r"(?<![a-z0-9])(?:us|eu|ap|sa|ca|me|af)-(?:east|west|north|south|central|northeast|southeast|northwest|southwest)-\d(?![a-z0-9])")
TENANT = re.compile(r"(?<![a-z0-9])tenant[-_]?[a-z0-9]+")
DIFF_CAP = 50
STOP = set("""about above after again also another because been before being between both could does doing down during
each further have having here into just more most must only other over same should some such than that their them then
there these they this those through under until very were what when where which while will with would your shall may not
""".split())


# --- config -----------------------------------------------------------------------

def scope_and_key(rel, settings):
    low = rel.lower()
    scope = set()
    for rx in (REGION, TENANT):
        for m in rx.finditer(low):
            scope.add(m.group(0))
        low = rx.sub(" ", low)
    toks = "|".join(sorted(map(re.escape, settings.scope_tokens), key=len, reverse=True))
    if toks:
        rx = re.compile(rf"(?<![a-z0-9])({toks})(?![a-z0-9])")
        for m in rx.finditer(low):
            scope.add(ALIASES.get(m.group(1), m.group(1)))
        low = rx.sub(" ", low)
    key = re.sub(r"\s+", "", low)
    key = re.sub(r"(?<=\w)[-_.]+(?=\.\w+$)", "", key)
    key = re.sub(r"/[-_.]+", "/", key)
    key = re.sub(r"[-_.]{2,}", ".", key)
    key = re.sub(r"/{2,}", "/", key)
    return key, frozenset(scope)


def suggest_winner(a, b, corpus):
    if a["priority"] != b["priority"]:
        return (a if a["priority"] > b["priority"] else b)["id"]
    ta, tb = file_date(a, corpus.meta(a))[0], file_date(b, corpus.meta(b))[0]
    if ta and tb and abs(ta - tb) >= 86400:
        return (a if ta > tb else b)["id"]
    return None


def config_conflicts(survivors, corpus, settings):
    groups = {}
    for r in survivors:
        if r["fmt"] in CONFIG_FORMATS and corpus.meta(r).get("flat"):
            groups.setdefault(scope_and_key(r["rel"], settings), []).append(r)
    out = []
    for (key, scope), members in sorted(groups.items(), key=lambda kv: kv[0][0]):
        if len(members) < 2 or len(members) > 12:
            continue
        for a, b in combinations(sorted(members, key=lambda r: r["id"]), 2):
            fa, fb = corpus.meta(a)["flat"], corpus.meta(b)["flat"]
            diffs = [{"key": k, a["id"]: fa[k], b["id"]: fb[k]} for k in sorted(fa.keys() & fb.keys()) if fa[k] != fb[k]]
            if diffs:
                out.append({"method": "config_key", "members": [a, b], "suggested_winner": suggest_winner(a, b, corpus),
                            "evidence": {"logical_file": key, "scope": sorted(scope), "diff_count": len(diffs),
                                         "diffs": diffs[:DIFF_CAP],
                                         "partial_parse": bool(corpus.meta(a).get("partial_parse") or corpus.meta(b).get("partial_parse"))}})
    return out


# --- prose --------------------------------------------------------------------------

NUM = re.compile(r"\$?\d[\d,]*(?:\.\d+)?\s*(?:%|percent|days?|hours?|minutes?|seconds?|ms|[kmgt]b|usd|users?|years?|months?|weeks?|requests?)?", re.I)
MODAL = re.compile(r"\b(?:must|shall|should|required|never|always|maximum|minimum|at least|at most|limit|no more than)\b", re.I)
NEG = re.compile(r"\b(?:not|never|no|cannot|can't|won't|don't|doesn't)\b", re.I)


def terms_of(norm):
    return [w for w in re.findall(r"[a-z]{4,}", norm) if w not in STOP]


def topic_terms(docs, corpus):
    """Top terms per doc by tf-idf, ignoring words only one document uses."""
    tfs = {d["id"]: Counter(terms_of(corpus.norm(d))) for d in docs}
    df = Counter(t for tf in tfs.values() for t in tf)
    n = len(docs)
    out = {}
    for d in docs:
        tf = tfs[d["id"]]
        scored = sorted((t for t in tf if df[t] >= 2), key=lambda t: (-(tf[t] * math.log((n + 1) / df[t])), t))
        out[d["id"]] = scored[:15]
    return out


def clean_sentence_source(text):
    text = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", text, flags=re.S)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    return re.sub(r"(?m)^[#>\-*\s|]+", "", text)


def claims_of(text):
    out = []
    for s in re.split(r"(?<=[.!?])\s+|\n+", clean_sentence_source(text)):
        s = s.strip()
        if not 20 <= len(s) <= 400:
            continue
        nums = {re.sub(r"s$", "", re.sub(r"[\s,$]", "", m.group(0).lower())) for m in NUM.finditer(s)}
        nums = {n for n in nums if n}
        if nums or MODAL.search(s):
            out.append({"text": s, "kw": set(terms_of(" ".join(re.findall(r"[a-z]+", s.lower())))),
                        "nums": nums, "neg": bool(NEG.search(s))})
        if len(out) >= 60:
            break
    return out


def prose_conflicts(survivors, corpus, settings):
    docs = [r for r in survivors if r["fmt"] not in CONFIG_FORMATS and r["kind"] != "unhandled"
            and r["fmt"] not in ("png", "jpg", "gif", "webp", "svg") and corpus.meta(r).get("words", 0) >= 30]
    docs.sort(key=lambda r: r["id"])
    terms = topic_terms(docs, corpus)
    clusters = []
    for d in docs:
        t = set(terms[d["id"]])
        if len(t) < 4:
            continue
        for c in clusters:
            if len(c["docs"]) < 40 and (len(t & c["seed"]) >= 4 or len(t & c["seed"]) / len(t | c["seed"]) >= 0.3):
                c["docs"].append(d)
                break
        else:
            clusters.append({"seed": t, "docs": [d]})
    claim_cache, out = {}, []
    for c in clusters:
        for a, b in combinations(c["docs"], 2):
            ca = claim_cache.setdefault(a["id"], claims_of(corpus.text(a)))
            cb = claim_cache.setdefault(b["id"], claims_of(corpus.text(b)))
            pairs = []
            for x in ca:
                for y in cb:
                    common = x["kw"] & y["kw"]
                    num_clash = len(common) >= 3 and x["nums"] and y["nums"] and x["nums"] != y["nums"]
                    neg_clash = len(common) >= 5 and x["neg"] != y["neg"]
                    if num_clash or neg_clash:
                        pairs.append((len(common) + (2 if num_clash and not (x["nums"] & y["nums"]) else 0), x, y, sorted(common)))
            if not pairs:
                continue
            pairs.sort(key=lambda p: -p[0])
            out.append({"method": "prose", "members": [a, b], "suggested_winner": suggest_winner(a, b, corpus),
                        "score": pairs[0][0] + len(pairs),
                        "evidence": {"topic_terms": sorted(set(terms[a["id"]]) & set(terms[b["id"]]))[:10],
                                     "claim_pairs": [{"a": p[1]["text"], "b": p[2]["text"], "shared_terms": p[3][:8],
                                                      "numbers_a": sorted(p[1]["nums"]), "numbers_b": sorted(p[2]["nums"])}
                                                     for p in pairs[:8]]}})
    return out


def packet_for_prose(pid, proposal, a, b, corpus, settings):
    return {
        "schema_version": SCHEMA_VERSION, "proposal_id": pid, "kind": "conflict",
        "question": "Do these two documents contradict each other on any claim? For each real contradiction give a "
                    "claim pair with a short quote from each side, then say which document should win and why. "
                    "If the candidate pairs are not real contradictions, say conflict=false.",
        "suggested_winner_by_script": proposal["suggested_winner"],
        "topic_terms": proposal["evidence"]["topic_terms"],
        "candidate_claim_pairs": proposal["evidence"]["claim_pairs"],
        "files": [{"file": r["id"], "source": r["source"], "priority": r["priority"], "path": r["rel"],
                   "commit_date": r.get("commit_date"), "excerpt": corpus.text(r)[:settings.excerpt_chars * 2]}
                  for r in (a, b)],
    }
