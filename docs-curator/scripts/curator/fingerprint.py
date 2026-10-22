"""Text fingerprints: normalized hash, shingles, MinHash sketch, SVG hash."""

import hashlib
import re
import xml.etree.ElementTree as ET

SKETCH_BINS = 128
BANDS, ROWS = 16, 8
FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)


def normalize(text):
    """Lowercase words only: no frontmatter, comments, markup or punctuation."""
    text = FRONTMATTER.sub(" ", text, count=1)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"[\W_]+", " ", text.lower())
    return " ".join(text.split())


def norm_hash(norm):
    return hashlib.sha256(norm.encode()).hexdigest()


def words(norm):
    return norm.split()


def shingle_set(norm, k=5):
    w = norm.split()
    if len(w) <= k:
        return {_h64(" ".join(w))} if w else set()
    return {_h64(" ".join(w[i:i + k])) for i in range(len(w) - k + 1)}


def _h64(s):
    return int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "big")


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def sketch(shingles):
    """One-permutation MinHash: the minimum hash in each of SKETCH_BINS bins."""
    bins = [None] * SKETCH_BINS
    for h in shingles:
        b, v = h % SKETCH_BINS, h // SKETCH_BINS
        if bins[b] is None or v < bins[b]:
            bins[b] = v
    return bins


def lsh_keys(bins):
    return [(i, tuple(bins[i * ROWS:(i + 1) * ROWS])) for i in range(BANDS)]


def svg_normalized_hash(raw):
    """Hash an SVG with whitespace and attribute order normalized."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return hashlib.sha256(re.sub(rb"\s+", b" ", raw).strip()).hexdigest()

    def canon(el):
        attrs = ",".join(f"{k}={' '.join(v.split())}" for k, v in sorted(el.attrib.items()))
        text = " ".join((el.text or "").split())
        kids = "".join(canon(c) for c in el)
        return f"<{el.tag} {attrs}>{text}{kids}</>"
    return hashlib.sha256(canon(root).encode()).hexdigest()
