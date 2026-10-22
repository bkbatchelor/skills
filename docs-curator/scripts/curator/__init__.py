"""docs-curator internals: shared helpers, config and settings.

Standard library only. The CLI in scripts/curate.py wires these modules
together; nothing here prints to stdout.
"""

import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import NoReturn

SCHEMA_VERSION = "1.0"
SKILL_DIR = Path(__file__).resolve().parent.parent.parent
PREFIX = "DOCS_CURATOR_"


def log(msg):
    print(f"docs-curator: {msg}", file=sys.stderr, flush=True)


def die(msg, code=1) -> NoReturn:
    log(msg)
    sys.exit(code)


# --- config ------------------------------------------------------------------

def read_env_file(path):
    out = {}
    try:
        for line in Path(path).expanduser().read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip().removeprefix("export ").strip()] = v.strip().strip("\"'")
    except FileNotFoundError:
        pass
    return out


def load_config():
    cfg = read_env_file(SKILL_DIR / "config.env")
    cfg.update({k: v for k, v in os.environ.items() if k.startswith(PREFIX)})
    return cfg


class Settings:
    """Typed view of the DOCS_CURATOR_* config."""

    def __init__(self, cfg=None):
        cfg = cfg if cfg is not None else load_config()
        g = lambda k, d: cfg.get(PREFIX + k, d)
        self.near_sim = float(g("NEAR_SIM", "0.90"))
        self.cross_sim = float(g("CROSS_FORMAT_SIM", "0.80"))
        self.family_sim = float(g("FAMILY_SIM", "0.50"))
        self.min_words = int(g("MIN_WORDS", "12"))
        self.packet_cap = int(g("PACKET_CAP", "200"))
        self.ocr = g("OCR", "0") == "1"
        self.xlsx_row_cap = int(g("XLSX_ROW_CAP", "200"))
        self.marker_chars = int(g("MARKER_CHARS", "3000"))
        self.excerpt_chars = int(g("EXCERPT_CHARS", "1500"))
        self.soffice_timeout = int(g("SOFFICE_TIMEOUT", "120"))
        self.scope_tokens = {t.strip().lower() for t in
                             g("SCOPE_TOKENS", "dev,development,test,qa,staging,stage,uat,prod,production,local").split(",")
                             if t.strip()}
        self.format_rank = parse_format_rank(g("FORMAT_RANK", "md=txt=html=csv>pptx=docx=xlsx=ppt=doc=xls>pdf>image"))

    def as_dict(self):
        return {k: (sorted(v) if isinstance(v, set) else v) for k, v in vars(self).items()}


def parse_format_rank(spec):
    rank = {}
    for i, group in enumerate(spec.split(">")):
        for fmt in group.split("="):
            rank[fmt.strip().lower()] = i
    return rank


IMAGE_FORMATS = {"png", "jpg", "gif", "webp", "svg"}


def format_rank(settings, fmt):
    r = settings.format_rank
    if fmt in r:
        return r[fmt]
    if fmt in IMAGE_FORMATS and "image" in r:
        return r["image"]
    return max(r.values(), default=0) + 1


# --- small helpers -----------------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def to_ts(iso):
    """ISO-8601 (or None) to a UTC timestamp; naive values count as UTC."""
    if not iso:
        return None
    try:
        d = dt.datetime.fromisoformat(iso.strip())
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.timestamp()


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def file_id(source, rel):
    return f"{source}:{rel}"


def slug(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-") or "source"
