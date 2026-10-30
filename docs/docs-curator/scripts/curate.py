#!/usr/bin/env python3
"""docs-curator: curate a read-only document folder into a Graphify staging tree.

  curate.py analyze --source SRC --out OUT   deterministic analysis, writes the LLM queue
  curate.py apply   --source SRC --out OUT   applies verdicts, builds OUT/staging, REPORT.md
  curate.py link    --source SRC --out OUT   symlinks SRC/graphify-out to OUT/graphify-out

--out defaults to ~/curated/<basename of SRC>. The source is only ever read, except that
`link` creates the one graphify-out symlink. Graphify is never run; its command is printed.
Code is kept 3.10-compatible.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

EXTRACT_VERSION = 1
WORKDIR = ".docs-curator"
SUPPORTED = {".pptx", ".pdf", ".md", ".xlsx", ".txt", ".docx"}
FORMAT_RANK = {"md": 0, "docx": 1, "pptx": 2, "xlsx": 3, "pdf": 4, "txt": 5}
SKIP_DIRS = {".git", "node_modules", "__pycache__", "graphify-out"}
IDENTICAL_TEXT_SIMILARITY = 0.999
MIN_TOKENS = 5
DEFAULT_ID_PATTERN = r"\b[A-Z][A-Z0-9]{1,9}-\d{1,6}\b"

DEFAULTS = {
    "embedding_backend": "fastembed",  # fastembed | tfidf
    "embedding_model": "BAAI/bge-small-en-v1.5",
    "near_duplicate_threshold": 0.90,
    "near_duplicate_action": "flag",  # flag | exclude
    "keeper_prefers_descriptive_name": True,
    "similarity_max_tokens": 50000,
    "subsumed_containment": 0.95,
    "subsumed_min_length_ratio": 0.20,
    "low_confidence_threshold": 0.75,
    "revision_chain_scope": "directory",  # directory | corpus
    "max_llm_clusters_per_run": 25,
    "llm_read_words": 6000,
    "report_group_member_limit": 5,
    "cluster_z": 1.0,
    "cluster_floor_fastembed": 0.78,
    "cluster_floor_tfidf": 0.25,
    "identifier_patterns": [DEFAULT_ID_PATTERN],
    "identifier_title_headers": ["id", "ticket", "key", "ref", "number"],
}

STOPWORDS = set(
    "the and for with from that this these those into over under about copy "
    "final latest current draft updated revised version policy document file".split()
)


# --------------------------------------------------------------------------- utils


def die(msg, code=2):
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def load_yaml(path):
    import yaml

    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config(out, explicit=None):
    cfg = dict(DEFAULTS)
    path = Path(explicit) if explicit else Path(out) / "config.yaml"
    if explicit and not path.exists():
        die(f"config file not found: {path}")
    if path.exists():
        user = load_yaml(path)
        if not isinstance(user, dict):
            die(f"{path} must be a mapping")
        unknown = sorted(set(user) - set(DEFAULTS))
        if unknown:
            die(f"unknown config keys in {path}: {', '.join(unknown)}")
        cfg.update(user)
    if cfg["embedding_backend"] not in ("fastembed", "tfidf"):
        die("embedding_backend must be fastembed or tfidf")
    if cfg["near_duplicate_action"] not in ("flag", "exclude"):
        die("near_duplicate_action must be flag or exclude")
    if cfg["revision_chain_scope"] not in ("directory", "corpus"):
        die("revision_chain_scope must be directory or corpus")
    return cfg


def load_overrides(out, explicit=None):
    path = Path(explicit) if explicit else Path(out) / "overrides.yaml"
    if explicit and not path.exists():
        die(f"overrides file not found: {path}")
    if not path.exists():
        return {}
    data = load_yaml(path)
    if isinstance(data, dict):
        data = data.get("overrides", [])
    result = {}
    for item in data or []:
        if not isinstance(item, dict) or item.get("action") not in ("include", "exclude") or not item.get("path"):
            die(f"bad overrides entry (need path and action include|exclude): {item!r}")
        result[str(item["path"])] = {"action": item["action"], "note": item.get("note", "")}
    return result


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def resolve_out(args):
    """--out, or ~/curated/<basename of --source> when it is not given."""
    if args.out:
        return Path(args.out).expanduser().resolve()
    return (Path("~/curated").expanduser() / Path(args.source).expanduser().resolve().name).resolve()


def check_paths(source, out):
    if not source.is_dir():
        die(f"source is not a directory: {source}")
    if out == source or source in out.parents:
        die(f"--out must not be inside --source ({out} is inside {source})")
    if out in source.parents:
        die(f"--source must not be inside --out ({source} is inside {out})")


def walk(source):
    for dirpath, dirnames, filenames in os.walk(source):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            full = Path(dirpath) / name
            if full.is_symlink() or not full.is_file():
                continue
            yield full


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------- extraction

_md = None


def extract_text(full, fmt):
    """Phase 1 extraction. .md/.txt are read as UTF-8; charset guessing is fallback only."""
    global _md
    if fmt in ("md", "txt"):
        raw = full.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = raw.decode("cp1252")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")
    else:
        # markitdown quietly falls back to plain text on a broken container, so check first
        if fmt in ("docx", "pptx", "xlsx") and not zipfile.is_zipfile(full):
            raise ValueError(f"not a valid {fmt} container")
        if fmt == "pdf" and not full.read_bytes()[:1024].lstrip().startswith(b"%PDF"):
            raise ValueError("not a valid PDF (missing %PDF header)")
        if _md is None:
            from markitdown import MarkItDown

            _md = MarkItDown()
        text = _md.convert(str(full)).text_content or ""
    return text.replace("\r\n", "\n").replace("\r", "\n")


_COMMENT = re.compile(r"<!--.*?-->", re.S)
_NOTES = re.compile(r"###\s*Notes:.*?(?=<!--\s*Slide number|\Z)", re.S | re.I)
_PAGE_LINE = re.compile(r"^\s*(?:page|slide)\s+\d+(?:\s+of\s+\d+)?\s*$", re.I | re.M)


def normalize(text, fmt=None):
    """Lowercase alphanumeric tokens, with slide/page markers and deck notes removed."""
    if fmt == "pptx":
        text = _NOTES.sub(" ", text)
    text = _COMMENT.sub(" ", text)
    text = _PAGE_LINE.sub(" ", text)
    return re.findall(r"[a-z0-9]+", text.lower())


def core_modified(path):
    if path.suffix.lower() not in (".docx", ".pptx", ".xlsx"):
        return None
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("docProps/core.xml").decode("utf-8", "replace")
        m = re.search(r"<dcterms:modified[^>]*>([^<]+)<", xml)
        return m.group(1).strip() if m else None
    except Exception:
        return None


def split_front_matter(text):
    """Return (meta|None, body, ok). ok is False when a front-matter block exists but won't parse."""
    m = re.match(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", text, re.S)
    if not m:
        return None, text, True
    try:
        import yaml

        meta = yaml.safe_load(m.group(1))
    except Exception:
        return None, text, False
    if not isinstance(meta, dict):
        return None, text, False
    return meta, text[m.end():], True


def describe(text, stem, limit=160):
    """Deterministic description: first H1/H2, else first non-empty line, else filename stem."""
    text = _COMMENT.sub("", text)
    chosen = None
    lines = [ln.strip() for ln in text.splitlines()]
    for ln in lines:
        m = re.match(r"^#{1,2}\s+(.+?)\s*#*$", ln)
        if m:
            chosen = m.group(1)
            break
    if chosen is None:
        for ln in lines:
            if ln and not re.fullmatch(r"[-=*_|\s]+", ln):
                chosen = ln
                break
    if chosen is None:
        return stem
    chosen = re.sub(r"[*_`]+", "", chosen)
    chosen = re.sub(r"^[#>\-\s|]+", "", chosen)
    chosen = " ".join(chosen.split())
    if not chosen:
        return stem
    if len(chosen) > limit:
        chosen = chosen[: limit - 1].rstrip() + "…"
    return chosen


# --------------------------------------------------------------- filename analysis

_AMBIGUOUS = {"final": 1, "latest": 1, "current": 1, "draft": -1}
_STRICT = {"updated", "revised", "update", "revision"}
_VERSION_WORDS = {"v", "ver", "version", "rev", "r"}


def parse_name(stem):
    """Split a filename stem into a normalized stem plus revision markers.

    Markers are read anywhere in the stem (both ends), not just at the end.
    """
    tokens = re.findall(r"[a-z]+|\d+(?:\.\d+)*", stem.lower())
    keep, version, strict, amb, markers = [], None, 0, 0, 0
    i = 0
    while i < len(tokens):
        t = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if t in _VERSION_WORDS and nxt and re.fullmatch(r"\d+(?:\.\d+)*", nxt):
            version = tuple(int(x) for x in nxt.split("."))
            markers += 1
            i += 2
            continue
        if t == "copy" and nxt == "of":
            strict += 1
            markers += 1
            i += 2
            continue
        if t == "copy" and i == len(tokens) - 1 and len(tokens) > 1:
            strict += 1
            markers += 1
            i += 1
            continue
        if t in _STRICT:
            strict += 1
            markers += 1
            i += 1
            continue
        if t in _AMBIGUOUS:
            amb += _AMBIGUOUS[t]
            markers += 1
            i += 1
            continue
        keep.append(t)
        i += 1
    return {"stem": "-".join(keep), "version": version, "strict": strict, "ambiguous": amb, "markers": markers}


_TEXT_VERSION = re.compile(
    r"^\W*(?:document\s+)?(?:version|revision|rev|ver)\W{0,4}v?(\d+(?:\.\d+)*)", re.I | re.M
)
_TEXT_DATE = re.compile(
    r"^\W*(?:last\s+)?(?:updated|revised|modified|date|effective(?:\s+date)?)\W{0,4}(\d{4})[-/](\d{2})[-/](\d{2})",
    re.I | re.M,
)


def text_signals(text):
    head = "\n".join(text.splitlines()[:60])
    v = _TEXT_VERSION.search(head)
    d = _TEXT_DATE.search(head)
    return {
        "text_version": [int(x) for x in v.group(1).split(".")] if v else None,
        "text_date": f"{d.group(1)}-{d.group(2)}-{d.group(3)}" if d else None,
    }


def descriptive_score(stem_tokens, text_tokens):
    words = {w for w in stem_tokens if len(w) >= 4 and w.isalpha() and w not in STOPWORDS}
    return len(words & set(text_tokens[:300]))


# ------------------------------------------------------------------- similarity


def dice(a, b):
    ca, cb = collections.Counter(a), collections.Counter(b)
    total = sum(ca.values()) + sum(cb.values())
    if not total:
        return 0.0
    return 2.0 * sum((ca & cb).values()) / total


def similarity(ta, tb, max_tokens):
    if not ta or not tb:
        return 0.0
    if len(ta) > max_tokens or len(tb) > max_tokens:
        return dice(ta, tb)  # multiset stand-in; reads lower, so it fails open
    from rapidfuzz.distance import Indel

    return Indel.normalized_similarity(ta, tb)


def shingle_set(tokens, n=2):
    if len(tokens) < n:
        return {int.from_bytes(hashlib.blake2b(" ".join(tokens).encode(), digest_size=8).digest(), "big")}
    return {
        int.from_bytes(hashlib.blake2b(" ".join(tokens[i : i + n]).encode(), digest_size=8).digest(), "big")
        for i in range(len(tokens) - n + 1)
    }


def candidate_pairs(shingles):
    """MinHash/LSH candidate pairs among {key: shingle set}."""
    from datasketch import MinHash, MinHashLSH

    lsh = MinHashLSH(threshold=0.35, num_perm=128)
    sigs = {}
    for key in sorted(shingles):
        m = MinHash(num_perm=128, seed=1)
        m.update_batch([h.to_bytes(8, "big") for h in shingles[key]])
        sigs[key] = m
        lsh.insert(key, m)
    pairs = set()
    for key, m in sigs.items():
        for other in lsh.query(m):
            if other != key:
                pairs.add(tuple(sorted((key, other))))
    return sorted(pairs)


def find_subsumed(docs, containment, min_ratio):
    """docs: {key: (tokens, shingle set)}. Returns {key: [(container, containment)]}."""
    index = collections.defaultdict(list)
    for k, (_, sh) in docs.items():
        for h in sh:
            index[h].append(k)
    found = {}
    for a, (ta, sha_) in sorted(docs.items()):
        if len(ta) < 20 or not sha_:
            continue
        sample = sorted(sha_)[:64]
        votes = collections.Counter()
        for h in sample:
            for k in index[h]:
                if k != a:
                    votes[k] += 1
        for b, n in sorted(votes.items()):
            tb, shb = docs[b]
            if n < 0.8 * len(sample) or len(ta) > (1 - min_ratio) * len(tb):
                continue
            c = len(sha_ & shb) / len(sha_)
            if c >= containment:
                found.setdefault(a, []).append((b, round(c, 4)))
    return found


def embed_matrix(texts, cfg):
    import numpy as np

    if cfg["embedding_backend"] == "tfidf":
        from sklearn.feature_extraction.text import TfidfVectorizer

        mat = TfidfVectorizer(sublinear_tf=True, stop_words="english").fit_transform(texts).toarray()
    else:
        try:
            from fastembed import TextEmbedding

            model = TextEmbedding(cfg["embedding_model"])
            mat = np.array(list(model.embed(texts)))
        except Exception as exc:  # model missing offline, no network, bad name
            die(
                f"fastembed could not load {cfg['embedding_model']!r}: {exc}\n"
                "Set 'embedding_backend: tfidf' in config.yaml to use the TF-IDF fallback."
            )
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def cluster_documents(keys, texts, cfg):
    """Topic clusters over keys. Returns (clusters as lists of keys, cut)."""
    import numpy as np

    if len(keys) < 2:
        return [], None
    mat = embed_matrix(texts, cfg)
    sims = mat @ mat.T
    iu = np.triu_indices(len(keys), 1)
    vals = sims[iu]
    floor = cfg["cluster_floor_" + cfg["embedding_backend"]]
    cut = max(floor, float(vals.mean() + cfg["cluster_z"] * vals.std()))
    parent = list(range(len(keys)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j in zip(*iu):
        if sims[i, j] >= cut:
            parent[find(int(i))] = find(int(j))
    groups = collections.defaultdict(list)
    for i, k in enumerate(keys):
        groups[find(i)].append(k)
    return [sorted(g) for g in groups.values() if len(g) >= 2], cut


def cluster_id(shas):
    return hashlib.sha256("\n".join(sorted(shas)).encode()).hexdigest()[:16]


# ---------------------------------------------------------------- revision chains


def _order(keys_by_member):
    members = sorted(keys_by_member)
    keys = [keys_by_member[m] for m in members]
    if any(k is None for k in keys) or len(set(map(repr, keys))) < len(keys):
        return None
    return [m for _, m in sorted(zip(keys, members), key=lambda t: (t[0], t[1]))]


def analyze_chain(members, info):
    """Order chain members oldest -> newest from independent signals."""
    members = sorted(members)
    names = {m: info[m]["name"] for m in members}
    has_marker = any(n["version"] or n["strict"] for n in names.values())
    fname = _order({m: (names[m]["version"] or (0,), names[m]["strict"]) for m in members}) if has_marker else None
    amb = _order({m: names[m]["ambiguous"] for m in members})
    tver = _order({m: (tuple(info[m]["text_version"]) if info[m]["text_version"] else None) for m in members})
    tdate = _order({m: info[m]["text_date"] for m in members})
    core = _order({m: info[m]["core_modified"] for m in members})
    mtime = _order({m: info[m]["mtime"] for m in members})
    text_orders = [o for o in (tver, tdate) if o]
    amb_counts = amb is not None and any(o == amb for o in text_orders)
    candidates = [("filename_marker", fname), ("text_version", tver), ("text_date", tdate), ("core_modified", core)]
    if amb_counts:
        candidates.insert(1, ("ambiguous_marker", amb))
    voting = [(n, o) for n, o in candidates if o is not None]
    if voting:
        chosen = voting[0][1]
    else:
        chosen = mtime
    agreeing = [n for n, o in voting if o == chosen]
    contradicting = [n for n, o in voting if o != chosen]
    return {
        "stem": names[members[0]]["stem"],
        "members": members,
        "order": chosen,
        "agreeing": agreeing,
        "contradicting": contradicting,
        "mtime_agrees": mtime is not None and mtime == chosen,
        "ambiguous_ignored": amb is not None and not amb_counts,
        "deterministic": bool(chosen) and len(agreeing) >= 2 and not contradicting,
    }


# ----------------------------------------------------------- identifier collisions


def id_sites(path, text, cfg):
    pats = [re.compile(p) for p in cfg["identifier_patterns"]]
    sites = []
    stem = Path(path).stem.replace("_", " ")  # \b does not fire before an underscore
    for p in pats:
        m = p.match(stem)
        if m:
            sites.append((m.group(0), "filename", stem[m.end():]))
    vocab = {h.lower() for h in cfg["identifier_title_headers"]}
    lines = text.splitlines()
    key_idx = None
    in_table = False
    for idx, ln in enumerate(lines):
        hm = re.match(r"^\s{0,3}#{1,6}\s+(.*)$", ln)
        if hm:
            for p in pats:
                m = p.match(hm.group(1))
                if m:
                    sites.append((m.group(0), "heading", hm.group(1)[m.end():]))
        if ln.lstrip().startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            nxt = lines[idx + 1] if idx + 1 < len(lines) else ""
            if not in_table and re.match(r"^\s*\|[\s:\-|]+\|\s*$", nxt):
                key_idx = next((i for i, c in enumerate(cells) if c.lower() in vocab), None)
                in_table = key_idx is not None
                continue
            if in_table and key_idx is not None and key_idx < len(cells) and not re.match(r"^[\s:\-|]+$", ln.strip()):
                for p in pats:
                    m = p.fullmatch(cells[key_idx])
                    if m:
                        rest = " ".join(c for i, c in enumerate(cells) if i != key_idx)
                        sites.append((m.group(0), "index_table", rest))
        else:
            in_table = False
            key_idx = None
    return sites


def _title_words(title):
    return {w for w in re.findall(r"[a-z]{3,}", title.lower()) if w not in STOPWORDS}


def find_collisions(site_map):
    """site_map: {path: [(id, site, title)]}. Report ids bound to disjoint titles in different files."""
    by_id = collections.defaultdict(list)
    for path, sites in site_map.items():
        for ident, site, title in sites:
            by_id[ident].append({"path": path, "site": site, "title": title.strip(" -:_.")})
    out = []
    for ident, entries in sorted(by_id.items()):
        if len({e["path"] for e in entries}) < 2:
            continue
        conflict = False
        for i, a in enumerate(entries):
            for b in entries[i + 1:]:
                if a["path"] == b["path"]:
                    continue
                wa, wb = _title_words(a["title"]), _title_words(b["title"])
                if wa and wb and len(wa & wb) / len(wa | wb) < 0.2:
                    conflict = True
        if conflict:
            out.append({"id": ident, "sites": entries})
    return out


# ------------------------------------------------------------------------ analyze


def cmd_analyze(args):
    source = Path(args.source).expanduser().resolve()
    out = resolve_out(args)
    check_paths(source, out)
    cfg = load_config(out, args.config)
    work = out / WORKDIR
    tdir = work / "text" / f"v{EXTRACT_VERSION}"
    tdir.mkdir(parents=True, exist_ok=True)

    files, texts, new_or_changed = [], {}, 0
    for full in walk(source):
        rel = full.relative_to(source).as_posix()
        ext = full.suffix.lower()
        st = full.stat()
        rec = {
            "path": rel,
            "ext": ext,
            "format": ext.lstrip("."),
            "size": st.st_size,
            "mtime": st.st_mtime,
            "mtime_ns": st.st_mtime_ns,
            "sha256": sha256_file(full),
            "status": "ok",
            "error": None,
        }
        if ext not in SUPPORTED:
            rec["status"] = "not_ingestible"
            files.append(rec)
            continue
        cache, err = tdir / f"{rec['sha256']}.md", tdir / f"{rec['sha256']}.err"
        if not cache.exists() and not err.exists():
            new_or_changed += 1
            try:
                cache.write_text(extract_text(full, rec["format"]), encoding="utf-8")
            except Exception as exc:
                err.write_text(f"{type(exc).__name__}: {exc}", encoding="utf-8")
        if err.exists() and not cache.exists():
            rec["status"] = "unreadable"
            rec["error"] = err.read_text(encoding="utf-8")
        else:
            texts[rel] = cache.read_text(encoding="utf-8")
            rec["core_modified"] = core_modified(full)
        files.append(rec)

    byp = {f["path"]: f for f in files}
    tokens = {}
    for p, t in texts.items():
        tokens[p] = normalize(t, byp[p]["format"])
        byp[p]["tokens"] = len(tokens[p])
        if not tokens[p]:
            byp[p]["status"] = "text_free"

    # exact groups and keeper choice -------------------------------------------
    def rank_key(p):
        f, name = byp[p], parse_name(Path(p).stem)
        desc = descriptive_score(name["stem"].split("-"), tokens.get(p, [])) if cfg["keeper_prefers_descriptive_name"] else 0
        return (FORMAT_RANK[f["format"]], -f.get("tokens", 0), -desc, name["markers"], p)

    by_sha = collections.defaultdict(list)
    for f in files:
        if f["path"] in texts:
            by_sha[f["sha256"]].append(f["path"])
    reps = {sha: min(ps, key=rank_key) for sha, ps in by_sha.items()}
    exact_groups = {sha: sorted(ps) for sha, ps in by_sha.items() if len(ps) > 1}

    # duplicate edges among representatives ------------------------------------
    comparable = {sha: p for sha, p in reps.items() if byp[p].get("tokens", 0) >= MIN_TOKENS}
    shingles = {sha: shingle_set(tokens[p]) for sha, p in comparable.items()}
    edges = []
    for a, b in candidate_pairs(shingles):
        pa, pb = comparable[a], comparable[b]
        sim = similarity(tokens[pa], tokens[pb], cfg["similarity_max_tokens"])
        if sim >= cfg["near_duplicate_threshold"]:
            kind = "cross" if byp[pa]["format"] != byp[pb]["format"] else "near"
            edges.append({"a": pa, "b": pb, "sim": round(sim, 4), "kind": kind})
    edges.sort(key=lambda e: (e["a"], e["b"]))

    parent = {p: p for p in comparable.values()}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in edges:
        parent[find(e["a"])] = find(e["b"])
    grp = collections.defaultdict(list)
    for p in parent:
        grp[find(p)].append(p)
    dup_groups = []
    for members in grp.values():
        if len(members) > 1:
            members = sorted(members)
            dup_groups.append({"keeper": min(members, key=rank_key), "members": members})
    dup_groups.sort(key=lambda g: g["keeper"])

    # documents that remain after exact and cross-format removal ------------------
    cross_excluded = set()
    for g in dup_groups:
        for m in g["members"]:
            if m != g["keeper"] and byp[m]["format"] != byp[g["keeper"]]["format"]:
                cross_excluded.add(m)
    alive = sorted(p for p in comparable.values() if p not in cross_excluded)

    # subsumption ---------------------------------------------------------------
    docs = {p: (tokens[p], shingle_set(tokens[p])) for p in alive}
    subsumed = []
    for a, containers in find_subsumed(docs, cfg["subsumed_containment"], cfg["subsumed_min_length_ratio"]).items():
        subsumed.append({"path": a, "containers": [{"path": b, "containment": c} for b, c in containers]})

    # topic clusters and revision chains ----------------------------------------
    cut = None
    clusters = []
    if len(alive) >= 2:
        snippets = [" ".join(re.findall(r"\S+", _COMMENT.sub(" ", texts[p]))[:400]) for p in alive]
        groups, cut = cluster_documents(alive, snippets, cfg)
        for members in groups:
            clusters.append({"id": cluster_id([byp[m]["sha256"] for m in members]), "members": members})
    cluster_of = {m: c["id"] for c in clusters for m in c["members"]}

    info = {}
    for p in alive:
        name = parse_name(Path(p).stem)
        sig = text_signals(texts[p])
        info[p] = {
            "name": name,
            "text_version": sig["text_version"],
            "text_date": sig["text_date"],
            "core_modified": byp[p].get("core_modified"),
            "mtime": byp[p]["mtime"],
        }
    chain_groups = collections.defaultdict(list)
    for p in alive:
        if p in cluster_of and info[p]["name"]["stem"]:
            directory = str(Path(p).parent) if cfg["revision_chain_scope"] == "directory" else ""
            chain_groups[(directory, info[p]["name"]["stem"], cluster_of[p])].append(p)
    chains = [analyze_chain(ms, info) for _, ms in sorted(chain_groups.items()) if len(ms) > 1]
    for c in chains:
        c["signals"] = {m: {k: info[m][k] for k in ("text_version", "text_date", "core_modified", "mtime")} for m in c["members"]}
        c["name_markers"] = {
            m: {k: info[m]["name"][k] for k in ("version", "strict", "ambiguous")} for m in c["members"]
        }

    # identifier collisions and naming anomalies ------------------------------------
    collisions = find_collisions({p: id_sites(p, texts[p], cfg) for p in sorted(reps.values()) if p in texts})
    anomalies = []
    for sha, ps in sorted(exact_groups.items()):
        if len({parse_name(Path(p).stem)["stem"] for p in ps}) > 1:
            anomalies.append({"kind": "exact", "kept": reps[sha], "paths": ps})
    for e in edges:
        if e["sim"] >= IDENTICAL_TEXT_SIMILARITY and parse_name(Path(e["a"]).stem)["stem"] != parse_name(Path(e["b"]).stem)["stem"]:
            anomalies.append({"kind": "text_identical", "kept": min((e["a"], e["b"]), key=rank_key), "paths": [e["a"], e["b"]]})

    # LLM queue -------------------------------------------------------------------
    verdict_dir = work / "work" / "verdicts"
    verdict_dir.mkdir(parents=True, exist_ok=True)
    reviewed = set()
    if verdict_dir.exists():
        for vf in verdict_dir.glob("*.json"):
            try:
                reviewed.add(json.loads(vf.read_text(encoding="utf-8")).get("cluster_id", vf.stem))
            except Exception:
                pass
    queue_dir = work / "work" / "queue"
    if queue_dir.exists():
        shutil.rmtree(queue_dir)
    queue_dir.mkdir(parents=True)
    ranked = sorted(clusters, key=lambda c: (-len(c["members"]), c["id"]))
    slots = cfg["max_llm_clusters_per_run"]
    for c in ranked:
        c["reviewed"] = c["id"] in reviewed
        c["queued"] = False
        if c["reviewed"]:
            continue
        if slots <= 0:
            continue
        slots -= 1
        c["queued"] = True
        item = {
            "cluster_id": c["id"],
            "read_words": cfg["llm_read_words"],
            "members": [
                {
                    "path": m,
                    "also_at": [x for x in exact_groups.get(byp[m]["sha256"], []) if x != m],
                    "format": byp[m]["format"],
                    "text_path": str(tdir / f"{byp[m]['sha256']}.md"),
                    "size_bytes": byp[m]["size"],
                    "tokens": byp[m]["tokens"],
                    "revision_signals": info[m]["name"] | {k: info[m][k] for k in ("text_version", "text_date", "core_modified", "mtime")},
                }
                for m in c["members"]
            ],
            "chains": [ch for ch in chains if ch["members"][0] in c["members"]],
            "near_duplicate_pairs": [e for e in edges if e["a"] in c["members"] and e["b"] in c["members"]],
        }
        write_json(queue_dir / f"{c['id']}.json", item)

    analysis = {
        "analysis_version": 1,
        "extract_version": EXTRACT_VERSION,
        "source": str(source),
        "files": files,
        "reps": reps,
        "exact_groups": exact_groups,
        "edges": edges,
        "dup_groups": dup_groups,
        "subsumed": subsumed,
        "chains": chains,
        "clusters": ranked,
        "cluster_cut": cut,
        "collisions": collisions,
        "anomalies": anomalies,
        "backend": cfg["embedding_backend"],
        "model": cfg["embedding_model"] if cfg["embedding_backend"] == "fastembed" else None,
    }
    write_json(work / "analysis.json", analysis)
    write_state(work, cfg, {"analyze": {"files": len(files), "new_or_changed": new_or_changed, "clusters": len(clusters), "queued": sum(c["queued"] for c in ranked)}})
    queued = sum(c["queued"] for c in ranked)
    print(f"analyzed {len(files)} files ({new_or_changed} new or changed); {len(clusters)} clusters, {queued} queued for review")
    print(f"queue: {queue_dir}")


def cmd_update(args):
    """Re-analyze after the source changed and report what was added, modified or removed."""
    out = resolve_out(args)
    work = out / WORKDIR
    ap = work / "analysis.json"
    if not ap.exists():
        die("no earlier analysis found; run 'analyze' first")
    old = {f["path"]: f["sha256"] for f in json.loads(ap.read_text(encoding="utf-8"))["files"]}
    cmd_analyze(args)
    an = json.loads(ap.read_text(encoding="utf-8"))
    new = {f["path"]: f["sha256"] for f in an["files"]}
    added = sorted(p for p in new if p not in old)
    modified = sorted(p for p in new if p in old and new[p] != old[p])
    removed = sorted(p for p in old if p not in new)
    touched = set(added) | set(modified)
    affected = [c["id"] for c in an["clusters"] if touched & set(c["members"])]
    queue = sorted(q.stem for q in (work / "work" / "queue").glob("*.json"))
    known = {c["id"] for c in an["clusters"]}
    vdir = work / "work" / "verdicts"
    stale = sorted(v.stem for v in vdir.glob("*.json") if v.stem not in known) if vdir.exists() else []
    changes = {
        "added": added,
        "modified": modified,
        "removed": removed,
        "unchanged": len(new) - len(added) - len(modified),
        "affected_clusters": affected,
        "queued_clusters": queue,
        "stale_verdicts": stale,
    }
    write_json(work / "changes.json", changes)
    write_state(work, load_config(out, args.config), {"update": {k: (len(v) if isinstance(v, list) else v) for k, v in changes.items()}})
    print(f"update: {len(added)} added, {len(modified)} modified, {len(removed)} removed, {changes['unchanged']} unchanged")
    for label, items in (("added", added), ("modified", modified), ("removed", removed)):
        for item in items[:20]:
            print(f"  {label}: {item}")
        if len(items) > 20:
            print(f"  ... {len(items) - 20} more {label}")
    print(f"{len(queue)} cluster(s) need review ({len(affected)} contain a new or modified file); {len(stale)} stale verdict(s) match no current cluster")
    print(f"changes: {work / 'changes.json'}")
    if not (added or modified or removed):
        print("nothing changed; staging is current")
    else:
        print("next: review the queued clusters, then run 'apply'")


def write_state(work, cfg, extra):
    path = work / "state.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    state.update(extra)
    state["config"] = cfg
    state["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    write_json(path, state)


# -------------------------------------------------------------------------- decide


def load_verdicts(work):
    """Read verdict files. Malformed ones are skipped with a warning (missing verdict = keep)."""
    verdicts, warnings = [], []
    vdir = work / "work" / "verdicts"
    for vf in sorted(vdir.glob("*.json")) if vdir.exists() else []:
        try:
            v = json.loads(vf.read_text(encoding="utf-8"))
            if not isinstance(v, dict):
                raise ValueError("not an object")
            v.setdefault("cluster_id", vf.stem)
            v["revisions"] = list(v.get("revisions") or [])
            v["conflicts"] = list(v.get("conflicts") or [])
            verdicts.append(v)
        except Exception as exc:
            warnings.append(f"verdict {vf.name} ignored: {exc}")
    return verdicts, warnings


def decide(an, cfg, overrides, verdicts):
    """Resolve an action/reason per file. Precedence:
    overrides -> exact -> cross-format -> near-duplicate (if exclude) -> superseded
    -> low_confidence -> near_duplicate_flag -> subsumed.
    Returns (decisions by path, warnings).
    """
    files = {f["path"]: f for f in an["files"]}
    dec, warnings = {}, []
    thr = cfg["low_confidence_threshold"]

    def put(path, action, reason, kept=None, evidence=None, confidence=None):
        dec[path] = {"action": action, "reason": reason, "kept_instead": kept, "evidence": evidence or {}, "confidence": confidence}

    for p, f in files.items():
        if f["status"] == "not_ingestible":
            put(p, "not_ingestible", "not_ingestible", evidence={"extension": f["ext"]})
        elif f["status"] == "unreadable":
            put(p, "unreadable", "unreadable", evidence={"error": f["error"]})

    reps = an["reps"]
    rep_paths = set(reps.values())
    for p, f in files.items():
        if p in dec or p in rep_paths:
            continue
        put(p, "exclude", "exact_duplicate", kept=reps[f["sha256"]], evidence={"sha256": f["sha256"]})

    edge_sim = {}
    for e in an["edges"]:
        edge_sim[(e["a"], e["b"])] = edge_sim[(e["b"], e["a"])] = e["sim"]
    flagged = {}
    for g in an["dup_groups"]:
        keeper = g["keeper"]
        for m in g["members"]:
            if m == keeper:
                continue
            sims = [edge_sim[(m, o)] for o in g["members"] if (m, o) in edge_sim]
            ev = {"similarity": max(sims) if sims else None, "to_keeper": edge_sim.get((m, keeper))}
            if files[m]["format"] != files[keeper]["format"]:
                put(m, "exclude", "format_duplicate", kept=keeper, evidence=ev)
            elif cfg["near_duplicate_action"] == "exclude":
                put(m, "exclude", "near_duplicate", kept=keeper, evidence=ev)
            else:
                flagged[m] = (keeper, ev)

    # exact copies of an excluded representative point at the final keeper
    for p, d in list(dec.items()):
        if d["reason"] == "exact_duplicate":
            r = reps[files[p]["sha256"]]
            if r in dec and dec[r]["action"] == "exclude":
                d["kept_instead"] = dec[r]["kept_instead"]

    def alive(p):
        return p in files and p not in dec

    # revisions -----------------------------------------------------------------
    verdict_rev = {}
    for v in verdicts:
        for r in v["revisions"]:
            try:
                sup, by = r["superseded"], r["superseded_by"]
                conf = float(r.get("confidence", 0))
            except (KeyError, TypeError, ValueError):
                warnings.append(f"verdict {v['cluster_id']}: malformed revision entry ignored")
                continue
            if sup not in files or by not in files or sup == by:
                warnings.append(f"verdict {v['cluster_id']}: revision names unknown paths ({sup} / {by})")
                continue
            verdict_rev[sup] = {"by": by, "confidence": conf, "rationale": r.get("rationale", ""), "unique_content": list(r.get("unique_content") or [])}
    handled = set()
    for ch in an["chains"]:
        if not ch["order"]:
            continue
        newest = ch["order"][-1]
        for p in ch["order"][:-1]:
            if not alive(p):
                continue
            handled.add(p)
            ev = {"agreeing": ch["agreeing"], "contradicting": ch["contradicting"], "mtime_agrees": ch["mtime_agrees"]}
            vr = verdict_rev.get(p)
            if ch["deterministic"]:
                if vr and vr["by"] != newest:
                    warnings.append(f"{p}: verdict says superseded by {vr['by']}, but signals say {newest}; signals kept")
                put(p, "exclude", "superseded", kept=newest, evidence=ev | {"verdict": bool(vr)}, confidence=vr["confidence"] if vr else None)
            elif vr and vr["confidence"] >= thr:
                put(p, "exclude", "superseded", kept=vr["by"], evidence=ev | {"rationale": vr["rationale"]}, confidence=vr["confidence"])
            else:
                put(p, "include", "low_confidence_keep", kept=newest, evidence=ev | {"verdict": bool(vr)}, confidence=vr["confidence"] if vr else None)
    for p, vr in sorted(verdict_rev.items()):
        if p in handled or not alive(p):
            continue
        if vr["confidence"] >= thr:
            put(p, "exclude", "superseded", kept=vr["by"], evidence={"rationale": vr["rationale"]}, confidence=vr["confidence"])
        else:
            put(p, "include", "low_confidence_keep", kept=vr["by"], evidence={"rationale": vr["rationale"]}, confidence=vr["confidence"])

    for p, (keeper, ev) in sorted(flagged.items()):
        # a flag that points at an excluded file would send the reader nowhere
        if p not in dec and dec.get(keeper, {}).get("action") != "exclude":
            put(p, "include", "near_duplicate_flag", kept=keeper, evidence=ev)
    for s in an["subsumed"]:
        p = s["path"]
        if p in dec:
            continue
        for c in s["containers"]:
            if alive(c["path"]) or (c["path"] in dec and dec[c["path"]]["action"] != "exclude"):
                put(p, "include", "subsumed_flag", kept=c["path"], evidence={"containment": c["containment"]})
                break

    for p, f in files.items():
        if p not in dec:
            ev = {"text_free": True} if f["status"] == "text_free" else {}
            put(p, "include", "unique", evidence=ev)

    # overrides win over everything except unreadable / not_ingestible --------------
    for p, o in overrides.items():
        if p not in files:
            warnings.append(f"override for unknown path ignored: {p}")
            continue
        if dec[p]["action"] in ("unreadable", "not_ingestible"):
            warnings.append(f"override cannot rescue {dec[p]['action']} file: {p}")
            continue
        put(p, "include" if o["action"] == "include" else "exclude", f"override_{o['action']}", evidence={"note": o["note"]})

    for p, d in dec.items():
        if d["action"] == "include" and files[p]["format"] == "pptx":
            d["action"] = "convert"
    return dec, warnings, verdict_rev


# --------------------------------------------------------------------------- apply


def staged_name(rel):
    return rel if rel.lower().endswith(".md") else rel + ".md"


def front_matter(fields):
    import yaml

    body = yaml.safe_dump(fields, sort_keys=False, allow_unicode=True, width=10000, default_flow_style=False)
    return f"---\n{body}---\n"


def make_doc(rel, fmt, sha, status, text, warnings):
    """Staged Markdown for one document, with front matter."""
    meta, body, ok = None, text, True
    if fmt == "md":
        meta, body, ok = split_front_matter(text)
        if not ok:
            warnings.append(f"{rel}: front matter did not parse; left in the body")
    fields = {
        "source_path": rel,
        "source_format": fmt,
        "sha256": sha,
        "status": status,
        "description": describe(body, Path(rel).stem),
    }
    if meta:
        fields["source_front_matter"] = meta
    return front_matter(fields) + ("\n" + body.lstrip("\n") if body.strip() else "")


def pptx_notes(path):
    from pptx import Presentation

    prs = Presentation(str(path))
    parts = []
    for i, slide in enumerate(prs.slides, 1):
        if slide.has_notes_slide:
            t = slide.notes_slide.notes_text_frame.text.strip() if slide.notes_slide.notes_text_frame else ""
            if t:
                parts.append(f"## Slide {i}\n\n{t}\n")
    return "\n".join(parts)


def convert_pptx(src, dest):
    """Convert one deck to PDF with LibreOffice. Serial, private profile, works on a copy."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("soffice not found")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        copy = tmp / "deck.pptx"
        shutil.copyfile(src, copy)
        outdir = tmp / "out"
        outdir.mkdir()
        proc = subprocess.run(
            [soffice, "--headless", f"-env:UserInstallation=file://{tmp / 'profile'}", "--convert-to", "pdf", "--outdir", str(outdir), str(copy)],
            capture_output=True, text=True, timeout=300,
        )
        pdf = outdir / "deck.pdf"
        if proc.returncode != 0 or not pdf.exists():
            raise RuntimeError((proc.stderr or proc.stdout or "no output").strip()[:300])
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(pdf, dest)


def norm_ws(s):
    return " ".join(s.lower().split())


def cmd_apply(args):
    source = Path(args.source).expanduser().resolve()
    out = resolve_out(args)
    check_paths(source, out)
    cfg = load_config(out, args.config)
    overrides = load_overrides(out, args.overrides)
    work = out / WORKDIR
    ap = work / "analysis.json"
    if not ap.exists():
        die("no analysis found; run 'analyze' first")
    an = json.loads(ap.read_text(encoding="utf-8"))
    files = {f["path"]: f for f in an["files"]}
    for p, f in files.items():
        full = source / p
        if not full.exists() or full.stat().st_size != f["size"] or full.stat().st_mtime_ns != f["mtime_ns"]:
            die(f"source changed since analyze ({p}); run 'analyze' again")
    tdir = work / "text" / f"v{an['extract_version']}"

    verdicts, warnings = load_verdicts(work)
    dec, dwarn, verdict_rev = decide(an, cfg, overrides, verdicts)
    warnings += dwarn
    known_clusters = {c["id"] for c in an["clusters"]}
    for v in verdicts:
        if v["cluster_id"] not in known_clusters:
            warnings.append(f"verdict for cluster {v['cluster_id']} matches no current cluster (stale?)")
        if v.get("partial_read"):
            warnings.append(f"verdict {v['cluster_id']} was written from a partial read")

    def text_of(p):
        return (tdir / f"{files[p]['sha256']}.md").read_text(encoding="utf-8")

    staging = out / "staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    pdf_cache = work / "pdf"
    written, sidecars, used = {}, [], set()

    def claim(rel, sha):
        name = rel
        if name in used:
            stem, dot, ext = rel.rpartition(".")
            name = f"{stem}.dup-{sha[:8]}.{ext}"
            warnings.append(f"staged name collision for {rel}; wrote {name}")
        used.add(name)
        return name

    def emit(rel, content):
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    for p in sorted(files):
        d, f = dec[p], files[p]
        if d["action"] not in ("include", "convert"):
            continue
        status = "unique" if d["reason"] == "unique" else d["reason"]
        if f["format"] == "pptx":
            pdf = pdf_cache / f"{f['sha256']}.pdf"
            try:
                if not pdf.exists():
                    convert_pptx(source / p, pdf)
            except Exception as exc:
                d.update(action="unreadable", reason="conversion_failed", evidence={"error": str(exc)})
                continue
            shutil.copyfile(pdf, _prep(staging / claim(p + ".pdf", f["sha256"])))
            try:
                notes = pptx_notes(source / p)
            except Exception as exc:
                notes = ""
                warnings.append(f"{p}: speaker notes unreadable ({exc})")
            desc = describe(text_of(p), Path(p).stem)
            fm = front_matter({"source_path": p, "source_format": "pptx", "sha256": f["sha256"], "status": status, "description": desc})
            emit(claim(p + ".notes.md", f["sha256"]), fm + ("\n" + notes if notes else "\nNo speaker notes.\n"))
            written[p] = p + ".pdf"
            continue
        rel = claim(staged_name(p), f["sha256"])
        emit(rel, make_doc(p, f["format"], f["sha256"], status, text_of(p), warnings))
        written[p] = rel

    # curated sidecars --------------------------------------------------------------
    for sup, vr in sorted(verdict_rev.items()):
        if dec.get(sup, {}).get("reason") == "superseded" and vr["unique_content"]:
            rel = f"_curated/historical/{staged_name(sup)}"
            emit(rel, make_doc(sup, files[sup]["format"], files[sup]["sha256"], "superseded", text_of(sup), warnings))
            sidecars.append(rel)

    conflicts = []
    for v in verdicts:
        for c in v["conflicts"]:
            stmts = []
            for s in c.get("statements") or []:
                path, quote = s.get("path"), s.get("quote", "")
                if path not in files:
                    warnings.append(f"conflict '{c.get('topic')}': unknown path {path}")
                    continue
                cached = tdir / f"{files[path]['sha256']}.md"
                verified = bool(quote) and cached.exists() and norm_ws(quote) in norm_ws(cached.read_text(encoding="utf-8"))
                if not verified:
                    warnings.append(f"conflict '{c.get('topic')}': quote not found verbatim in {path}")
                stmts.append({"path": path, "quote": quote, "location": s.get("location", ""), "verified": verified})
            conflicts.append({"topic": c.get("topic", ""), "statements": stmts, "rationale": c.get("rationale", ""), "cluster_id": v["cluster_id"]})
    if conflicts:
        body = ["# Conflicts between documents", ""]
        for i, c in enumerate(conflicts, 1):
            body += [f"## {i}. {c['topic']}", ""]
            for s in c["statements"]:
                loc = f" ({s['location']})" if s["location"] else ""
                flag = "" if s["verified"] else " [quote not verified]"
                body += [f"- `{s['path']}`{loc}: \"{s['quote']}\"{flag}"]
            if c["rationale"]:
                body += ["", c["rationale"]]
            body.append("")
        text = "\n".join(body)
        fm = front_matter({
            "source_path": "_curated/CONFLICTS.md", "source_format": "generated", "sha256": sha256_text(text),
            "status": "generated", "description": f"{len(conflicts)} conflict(s) found between documents in the corpus",
        })
        emit("_curated/CONFLICTS.md", fm + "\n" + text)
        sidecars.append("_curated/CONFLICTS.md")
    write_json(work / "conflicts.json", conflicts)

    # outputs -----------------------------------------------------------------------
    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    with open(work / "decisions.jsonl", "w", encoding="utf-8") as fh:
        for p in sorted(files):
            d = dec[p]
            row = {"run_id": run_id, "path": p, "sha256": files[p]["sha256"], **{k: d[k] for k in ("action", "reason", "kept_instead", "evidence", "confidence")}}
            fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    report = build_report(an, cfg, dec, files, verdicts, conflicts, sidecars, warnings, out, source)
    (work / "REPORT.md").write_text(report, encoding="utf-8")
    counts = collections.Counter(d["action"] for d in dec.values())
    write_state(work, cfg, {"apply": {"run_id": run_id, "counts": dict(counts), "overrides": len(overrides), "warnings": len(warnings)}})
    print(f"apply complete: {counts.get('include', 0) + counts.get('convert', 0)} staged, {counts.get('exclude', 0)} excluded, "
          f"{counts.get('unreadable', 0)} unreadable, {counts.get('not_ingestible', 0)} not ingestible")
    print(f"report: {work / 'REPORT.md'}")
    print(f"next: curate.py link --source {source} --out {out}   (graphify-out/ then lands in {out}, not the project)")
    print(f"then: cd {source} && /graphify {staging}")


def cmd_link(args):
    """Point <source>/graphify-out at <out>/graphify-out so Graphify's output stays out of the project.

    This is the only write the skill makes under --source: one symlink.
    """
    source = Path(args.source).expanduser().resolve()
    out = resolve_out(args)
    check_paths(source, out)
    target = out / "graphify-out"
    target.mkdir(parents=True, exist_ok=True)
    link = source / "graphify-out"
    if link.is_symlink():
        if Path(os.readlink(link)).resolve() == target.resolve():
            print(f"link already in place: {link} -> {target}")
            return
        die(f"{link} is a symlink to {os.readlink(link)}; remove it yourself if you want it repointed")
    if link.exists():
        die(f"{link} already exists and is not a symlink; move it aside (it may be an earlier graph) and re-run")
    link.symlink_to(target, target_is_directory=True)
    print(f"linked: {link} -> {target}")
    print(f"next: cd {source} && /graphify {out / 'staging'}")


def _prep(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def cap(items, limit):
    items = list(items)
    shown = ", ".join(f"`{x}`" for x in items[:limit])
    return shown + (f" (+{len(items) - limit} more)" if len(items) > limit else "")


def build_report(an, cfg, dec, files, verdicts, conflicts, sidecars, warnings, out, source):
    lim = cfg["report_group_member_limit"]
    by_reason = collections.defaultdict(list)
    for p, d in sorted(dec.items()):
        by_reason[d["reason"]].append(p)
    totals = collections.Counter(d["action"] for d in dec.values())
    L = ["# docs-curator report", "", f"Source: `{source}`  ", f"Output: `{out}`", "", "## Totals", ""]
    L += [f"- Files scanned: {len(files)}"] + [f"- {a}: {n}" for a, n in sorted(totals.items())]
    L += [f"- Embedding backend: {an['backend']}" + (f" ({an['model']})" if an.get("model") else ""), ""]

    L += ["## Excluded duplicates", ""]
    dups = [p for r in ("exact_duplicate", "format_duplicate", "near_duplicate") for p in by_reason.get(r, [])]
    groups = collections.defaultdict(list)
    for p in dups:
        groups[(dec[p]["kept_instead"], dec[p]["reason"])].append(p)
    for (kept, reason), ms in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])):
        L.append(f"- `{kept}` kept; {reason}: {cap(ms, lim)}")
    L += ["- none"] if not groups else []
    L.append("")

    L += ["## Filed under conflicting names", ""]
    for a in an["anomalies"]:
        L.append(f"- ({a['kind']}) kept `{a['kept']}`; also: {cap([p for p in a['paths'] if p != a['kept']], lim)}")
    L += ["- none"] if not an["anomalies"] else []
    L.append("")

    L += ["## Identifier collisions", ""]
    for c in an["collisions"]:
        sites = "; ".join(f"`{s['path']}` ({s['site']}: {s['title'] or '-'})" for s in c["sites"][:lim])
        L.append(f"- **{c['id']}**: {sites}")
    L += ["- none"] if not an["collisions"] else []
    L.append("")

    L += ["## Superseded", ""]
    for p in by_reason.get("superseded", []):
        L.append(f"- `{p}` superseded by `{dec[p]['kept_instead']}`" + (" (historical copy written)" if any(s.endswith(staged_name(p)) for s in sidecars) else ""))
    L += ["- none"] if not by_reason.get("superseded") else []
    L.append("")

    L += ["## Other exclusions", ""]
    others = [p for p, d in sorted(dec.items()) if d["action"] == "exclude" and d["reason"] not in ("exact_duplicate", "format_duplicate", "near_duplicate", "superseded")]
    L += [f"- `{p}`: {dec[p]['reason']}" for p in others] or ["- none"]
    L.append("")

    L += ["## Flagged but kept", ""]
    for r in ("near_duplicate_flag", "subsumed_flag", "low_confidence_keep"):
        for p in by_reason.get(r, []):
            L.append(f"- `{p}`: {r}, see `{dec[p]['kept_instead']}`")
    for p, f in sorted(files.items()):
        if f["status"] == "text_free":
            L.append(f"- `{p}`: text-free document (staged with an empty body, no OCR)")
    flagged_any = any(by_reason.get(r) for r in ("near_duplicate_flag", "subsumed_flag", "low_confidence_keep")) or any(f["status"] == "text_free" for f in files.values())
    L += ["- none"] if not flagged_any else []
    L.append("")

    L += ["## Unreadable", ""]
    L += [f"- `{p}`: {dec[p]['reason']} ({str(dec[p]['evidence'].get('error', ''))[:120]})" for p in by_reason.get("unreadable", []) + by_reason.get("conversion_failed", [])] or ["- none"]
    L += ["", "## Not ingestible", ""]
    L += [f"- `{p}`" for p in by_reason.get("not_ingestible", [])] or ["- none"]
    L += ["", "## Sidecars written into staging", ""]
    L += [f"- `{s}`" for s in sidecars] or ["- none"]

    pending = [c for c in an["clusters"] if not c["reviewed"] and c["id"] not in {v["cluster_id"] for v in verdicts}]
    L += ["", "## LLM queue", ""]
    L.append(f"- Clusters: {len(an['clusters'])}; reviewed (verdict present): {len(an['clusters']) - len(pending)}; pending: {len(pending)}")
    for c in pending:
        L.append(f"  - `{c['id']}` {'(queued)' if c.get('queued') else '(deferred past max_llm_clusters_per_run)'}: {cap(c['members'], lim)}")
    L += ["- conflicts recorded: %d" % len(conflicts)]
    if warnings:
        L += ["", "## Warnings", ""] + [f"- {w}" for w in warnings]
    L += ["", "## Staging method", "",
          "Generated. Markdown is written from the Phase 1 cached extraction, with front matter. Kept `.pptx` decks are converted to PDF with LibreOffice (serial, private profile) and paired with a `.notes.md` sidecar. Nothing is copied or linked from the source.",
          "", "## Next step", "", f"Run Graphify yourself (this skill never does): `/graphify {out / 'staging'}`", ""]
    return "\n".join(L)


# ----------------------------------------------------------------------------- cli


def build_parser():
    ap = argparse.ArgumentParser(prog="curate.py", description="Curate a read-only document folder into a Graphify staging tree.")
    sub = ap.add_subparsers(dest="command", required=True)
    for name, fn, help_ in (
        ("analyze", cmd_analyze, "inventory, extract, group duplicates, find revision chains and clusters, write the LLM queue"),
        ("update", cmd_update, "re-analyze after files were added, modified or removed; report the changes and queue only the affected clusters"),
        ("apply", cmd_apply, "apply verdicts and overrides, build staging/, REPORT.md and decisions.jsonl"),
        ("link", cmd_link, "symlink <source>/graphify-out to <out>/graphify-out (the only write under --source)"),
    ):
        p = sub.add_parser(name, help=help_, description=help_)
        p.add_argument("--source", required=True, help="read-only source folder")
        p.add_argument("--out", help="output folder, outside --source (default: ~/curated/<basename of --source>)")
        p.add_argument("--config", help="config.yaml (default: <out>/config.yaml)")
        p.add_argument("--overrides", help="overrides.yaml (default: <out>/overrides.yaml)")
        p.set_defaults(fn=fn)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
