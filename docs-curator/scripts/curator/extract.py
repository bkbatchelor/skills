"""Turn each file into Markdown text plus metadata, cached by sha256.

cache/text/<sha>.md   the extracted text
cache/meta/<sha>.json title, dates, fingerprints, flattened config, markers

pptx, docx and xlsx are read from their zip XML. pdf uses pdftotext and
pdfinfo. Legacy office formats go through soffice into the modern formats.
"""

import configparser
import csv
import datetime as dt
import io
import json
import re
import shutil
import subprocess
import tempfile
import tomllib
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from . import SCHEMA_VERSION, log, read_json, write_json
from .fingerprint import norm_hash, normalize, shingle_set, sketch, svg_normalized_hash

EXTRACTOR_VERSION = 2
LEGACY = {"ppt": "pptx", "doc": "docx", "xls": "xlsx"}
TEXT_NATIVE = {"md", "txt", "yaml", "json"}
IMAGES = {"png", "jpg", "gif", "webp", "svg"}

MARKER_RE = re.compile(r"\b(?:DEPRECATED|SUPERSEDED|OBSOLETE)\b"
                       r"|(?i:\bthis\s+(?:document|doc|page|file)\s+(?:is|has\s+been)\s+(?:deprecated|superseded|obsolete))")
REPLACED_RE = re.compile(r"(?i)\b(?:replaced|superseded)\s+by\s+[`\"'*_\[(<]*([^\s`\"'*\])>,;]+)")
MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
DATE_LABEL = re.compile(
    r"(?im)\b(?:last\s+(?:updated|modified|revised)|updated|revised|modified|date|as\s+of|effective)\b"
    r"[^\n\d]{0,20}(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|[A-Za-z]{3,9}\.?\s+\d{1,2},?\s+\d{4})")


class ExtractError(Exception):
    pass


def local(tag):
    return tag.rsplit("}", 1)[-1]


# --- cache entry point ---------------------------------------------------------

def extract(rec, settings, cache_dir, force=False):
    """Return (meta, cache_hit) for one file record."""
    cache_dir = Path(cache_dir)
    sha = rec["sha256"]
    tpath, mpath = cache_dir / "text" / f"{sha}.md", cache_dir / "meta" / f"{sha}.json"
    meta = None if force else read_json(mpath)
    if (meta and meta.get("extractor") == EXTRACTOR_VERSION and meta.get("format") == rec["fmt"]
            and meta.get("ocr_setting") == settings.ocr and (tpath.exists() or not meta.get("has_text"))):
        return meta, True
    meta = {"schema_version": SCHEMA_VERSION, "extractor": EXTRACTOR_VERSION, "sha256": sha,
            "format": rec["fmt"], "ocr_setting": settings.ocr, "title": None, "dates": {},
            "flat": None, "partial_parse": False, "error": None, "notes": [], "has_text": False}
    text = ""
    try:
        text = extract_text(rec, settings, meta)
    except (ExtractError, OSError, zipfile.BadZipFile, ET.ParseError, subprocess.SubprocessError, ValueError) as e:
        meta["error"] = f"{type(e).__name__}: {e}"
        log(f"extract failed for {rec['id']}: {meta['error']}")
    finalize(meta, text, rec, settings)
    if text:
        tpath.parent.mkdir(parents=True, exist_ok=True)
        tpath.write_text(text)
    elif tpath.exists():
        tpath.unlink()
    write_json(mpath, meta)
    return meta, False


def finalize(meta, text, rec, settings):
    meta["has_text"] = bool(text)
    norm = normalize(text)
    n = len(norm.split())
    meta["words"] = n
    meta["norm_hash"] = norm_hash(norm) if n >= 3 else None
    meta["sketch"] = sketch(shingle_set(norm)) if n >= settings.min_words else None
    head = text[:settings.marker_chars]
    keyword, repl = MARKER_RE.search(head), REPLACED_RE.search(head)
    meta["marker"] = {"keyword": bool(keyword), "target": repl.group(1).rstrip(".:") if repl else None} \
        if (keyword or repl) and rec["fmt"] not in IMAGES else None
    if text and "content" not in meta["dates"]:
        d = content_date(head)
        if d:
            meta["dates"]["content"] = d
    if not meta["title"] and text:
        m = re.search(r"(?m)^#{1,3}\s+(.+?)\s*$", text)
        meta["title"] = m.group(1) if m else None


def content_date(head):
    best = None
    for m in DATE_LABEL.finditer(head):
        d = parse_loose_date(m.group(1))
        if d and (best is None or d > best):
            best = d
    return best.isoformat() if best else None


def parse_loose_date(s):
    s = s.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return dt.date.fromisoformat(s)
        if "/" in s:
            mth, day, year = (int(x) for x in s.split("/"))
            return dt.date(year, mth, day)
        m = re.fullmatch(r"([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", s)
        if m and m.group(1).lower() in MONTHS:
            return dt.date(int(m.group(3)), MONTHS.index(m.group(1).lower()) + 1, int(m.group(2)))
    except ValueError:
        pass
    return None


# --- dispatch ------------------------------------------------------------------

def extract_text(rec, settings, meta):
    path, fmt = Path(rec["abs"]), rec["fmt"]
    if fmt in TEXT_NATIVE:
        text = read_text(path)
        if fmt in ("yaml", "json"):
            flatten_into(meta, fmt, text)
        return text
    if fmt in ("toml", "ini", "properties"):
        raw = read_text(path)
        flatten_into(meta, fmt, raw)
        return f"# {path.name}\n\n```{fmt}\n{raw.rstrip()}\n```\n"
    if fmt == "pptx":
        return pptx_text(path, meta)
    if fmt == "docx":
        return docx_text(path, meta)
    if fmt == "xlsx":
        return xlsx_text(path, meta, settings)
    if fmt == "pdf":
        return pdf_text(path, meta, settings)
    if fmt in LEGACY:
        return legacy_text(path, fmt, meta, settings)
    if fmt == "html":
        return html_text(read_text(path))
    if fmt == "csv":
        return csv_text(read_text(path), settings.xlsx_row_cap)
    if fmt in IMAGES:
        return image_text(path, fmt, meta, settings)
    raise ExtractError(f"no extractor for .{fmt}")


def read_text(path):
    return Path(path).read_bytes().decode("utf-8", errors="replace").replace("\r\n", "\n")


# --- office --------------------------------------------------------------------

def para_text(p):
    out = []
    for el in p.iter():
        t = local(el.tag)
        if t == "t" and el.text:
            out.append(el.text)
        elif t in ("br", "tab"):
            out.append(" ")
    return "".join(out).strip()


def core_props(z, meta):
    if "docProps/core.xml" not in z.namelist():
        return
    for el in ET.fromstring(z.read("docProps/core.xml")):
        t, v = local(el.tag), (el.text or "").strip()
        if t == "title" and v:
            meta["title"] = v
        elif t == "created" and v:
            meta["dates"]["created"] = v
        elif t == "modified" and v:
            meta["dates"]["modified"] = v


def rels(z, name):
    if name not in z.namelist():
        return {}
    return {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read(name))}


def pptx_text(path, meta):
    with zipfile.ZipFile(path) as z:
        core_props(z, meta)
        slides = sorted((int(m.group(1)), n) for n in z.namelist() if (m := re.fullmatch(r"ppt/slides/slide(\d+)\.xml", n)))
        parts = []
        for num, name in slides:
            paras = [t for t in (para_text(p) for p in ET.fromstring(z.read(name)).iter() if local(p.tag) == "p") if t]
            parts.append(f"<!-- slide {num} -->")
            for i, t in enumerate(paras):
                parts.append(f"## {t}" if i == 0 else f"- {t}")
            for target in rels(z, f"ppt/slides/_rels/slide{num}.xml.rels").values():
                if "notesSlide" in target:
                    notes = f"ppt/notesSlides/{Path(target).name}"
                    if notes in z.namelist():
                        nt = [t for t in (para_text(p) for p in ET.fromstring(z.read(notes)).iter() if local(p.tag) == "p") if t and not t.isdigit()]
                        if nt:
                            parts.append("<!-- notes -->")
                            parts.extend(f"> {t}" for t in nt)
            parts.append("")
        return "\n".join(parts).strip() + "\n"


def md_table(rows):
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [[c.replace("|", "\\|").replace("\n", " ") for c in r] + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def docx_text(path, meta):
    with zipfile.ZipFile(path) as z:
        core_props(z, meta)
        body = next((e for e in ET.fromstring(z.read("word/document.xml")) if local(e.tag) == "body"), None)
        if body is None:
            raise ExtractError("no w:body")
        out = []
        for el in body:
            tag = local(el.tag)
            if tag == "p":
                text = para_text(el)
                if not text:
                    continue
                style = next((s.get(k) for s in el.iter() if local(s.tag) == "pStyle" for k in s.attrib if local(k) == "val"), "") or ""
                m = re.fullmatch(r"(?i)heading\s*(\d)", style)
                if m:
                    out.append("#" * min(int(m.group(1)), 6) + " " + text)
                elif style.lower() == "title":
                    out.append("# " + text)
                elif any(local(e.tag) == "numPr" for e in el.iter()):
                    out.append("- " + text)
                else:
                    out.append(text)
            elif tag == "tbl":
                rows = [[" ".join(para_text(p) for p in tc.iter() if local(p.tag) == "p").strip()
                         for tc in tr if local(tc.tag) == "tc"]
                        for tr in el if local(tr.tag) == "tr"]
                out.append(md_table(rows))
        return "\n\n".join(out).strip() + "\n"


def col_index(ref):
    letters = re.match(r"[A-Za-z]+", ref).group(0).upper()
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_text(path, meta, settings):
    with zipfile.ZipFile(path) as z:
        core_props(z, meta)
        names = z.namelist()
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = ["".join(t.text or "" for t in si.iter() if local(t.tag) == "t")
                      for si in ET.fromstring(z.read("xl/sharedStrings.xml")) if local(si.tag) == "si"]
        wb_rels = rels(z, "xl/_rels/workbook.xml.rels")
        out = []
        for sheet in (e for e in ET.fromstring(z.read("xl/workbook.xml")).iter() if local(e.tag) == "sheet"):
            rid = next((v for k, v in sheet.attrib.items() if local(k) == "id"), None)
            target = wb_rels.get(rid, "")
            part = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
            if part not in names:
                continue
            rows, total = [], 0
            for row in (e for e in ET.fromstring(z.read(part)).iter() if local(e.tag) == "row"):
                total += 1
                if total > settings.xlsx_row_cap:
                    continue
                cells = {}
                for c in (e for e in row if local(e.tag) == "c"):
                    v = next((e.text or "" for e in c if local(e.tag) == "v"), "")
                    ctype = c.get("t")
                    if ctype == "s" and v.isdigit() and int(v) < len(shared):
                        v = shared[int(v)]
                    elif ctype == "inlineStr":
                        v = "".join(t.text or "" for t in c.iter() if local(t.tag) == "t")
                    elif v.endswith(".0"):
                        v = v[:-2]
                    cells[col_index(c.get("r", "A1"))] = v
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
            out.append(f"## {sheet.get('name', 'Sheet')}\n\n{md_table([r for r in rows if r])}")
            if total > settings.xlsx_row_cap:
                out.append(f"_… {total - settings.xlsx_row_cap} more rows not shown_")
        return "\n\n".join(out).strip() + "\n"


def legacy_text(path, fmt, meta, settings):
    target = LEGACY[fmt]
    if not shutil.which("soffice"):
        raise ExtractError("soffice is not installed (needed for legacy .%s)" % fmt)
    with tempfile.TemporaryDirectory(prefix="docs-curator-") as td:
        cmd = ["soffice", f"-env:UserInstallation=file://{td}/profile", "--headless",
               "--convert-to", target, "--outdir", td, str(path)]
        subprocess.run(cmd, capture_output=True, timeout=settings.soffice_timeout, check=False)
        out = Path(td) / f"{path.stem}.{target}"
        if not out.exists():
            raise ExtractError(f"soffice could not convert .{fmt}")
        fn = {"pptx": lambda: pptx_text(out, meta), "docx": lambda: docx_text(out, meta),
              "xlsx": lambda: xlsx_text(out, meta, settings)}[target]
        text = fn()
    meta["notes"].append(f"converted from .{fmt} with soffice")
    return text


# --- pdf, html, csv, images ------------------------------------------------------

def pdf_text(path, meta, settings):
    if not shutil.which("pdftotext"):
        raise ExtractError("pdftotext is not installed")
    r = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", str(path), "-"], capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        raise ExtractError(f"pdftotext: {r.stderr.strip()[:200]}")
    info = subprocess.run(["pdfinfo", "-isodates", str(path)], capture_output=True, text=True, errors="replace").stdout
    for line in info.splitlines():
        k, _, v = line.partition(":")
        v = v.strip()
        if k == "Title" and v:
            meta["title"] = v
        elif k == "CreationDate" and v:
            meta["dates"]["created"] = v
        elif k == "ModDate" and v:
            meta["dates"]["modified"] = v
    text = re.sub(r"[ \t]+\n", "\n", r.stdout.replace("\f", "\n\n")).strip()
    if len(text) < 20:
        meta["notes"].append("no text layer")
        if settings.ocr and shutil.which("tesseract") and shutil.which("pdftoppm"):
            text = ocr_pdf(path)
            meta["notes"].append("text from OCR")
    return text + "\n" if text else ""


def ocr_pdf(path):
    with tempfile.TemporaryDirectory(prefix="docs-curator-") as td:
        subprocess.run(["pdftoppm", "-r", "150", "-png", str(path), f"{td}/p"], capture_output=True, timeout=600)
        pages = sorted(Path(td).glob("p*.png"))
        return "\n\n".join(tesseract(p) for p in pages).strip()


def tesseract(png):
    r = subprocess.run(["tesseract", str(png), "-", "-l", "eng"], capture_output=True, text=True, errors="replace", timeout=300)
    return r.stdout.strip()


def image_text(path, fmt, meta, settings):
    if fmt == "svg":
        meta["svg_hash"] = svg_normalized_hash(Path(path).read_bytes())
    if settings.ocr and shutil.which("tesseract") and fmt != "svg":
        text = tesseract(path)
        if text:
            meta["notes"].append("text from OCR")
            meta["ocr"] = True
        return text
    return ""


class _HTML(HTMLParser):
    SKIP = {"script", "style", "head", "noscript"}
    BLOCK = {"p", "div", "br", "tr", "section", "article", "ul", "ol", "table", "pre", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.title, self._in_title = [], 0, None, False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in ("td", "th"):
            self.out.append(" | ")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        if tag == "title":
            self._in_title = False
        if re.fullmatch(r"h[1-6]", tag) or tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title = (self.title or "") + data.strip()
        if not self.skip:
            self.out.append(data)


def html_text(raw):
    p = _HTML()
    p.feed(raw)
    text = "".join(p.out)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()
    return (f"# {p.title}\n\n" if p.title and not text.startswith("#") else "") + text + "\n"


def csv_text(raw, cap):
    rows = list(csv.reader(io.StringIO(raw)))
    shown = md_table(rows[:cap + 1])
    extra = f"\n\n_… {len(rows) - cap - 1} more rows not shown_" if len(rows) > cap + 1 else ""
    return shown + extra + "\n" if shown else ""


# --- config flattening -----------------------------------------------------------

def scalar(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip()


def flatten_obj(obj, prefix="", out=None):
    out = {} if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten_obj(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            flatten_obj(v, f"{prefix}[{i}]", out)
    else:
        out[prefix] = scalar(obj)
    return out


def flatten_into(meta, fmt, text):
    try:
        if fmt == "json":
            meta["flat"] = flatten_obj(json.loads(text))
        elif fmt == "toml":
            meta["flat"] = flatten_obj(tomllib.loads(text))
        elif fmt == "ini":
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            cp.optionxform = str
            cp.read_string(text if re.search(r"(?m)^\s*\[", text) else "[DEFAULT]\n" + text)
            meta["flat"] = {(k if s == "DEFAULT" else f"{s}.{k}"): scalar(v)
                            for s in cp.sections() + ["DEFAULT"] for k, v in cp.items(s)
                            if s != "DEFAULT" or k in cp.defaults()}
        elif fmt == "properties":
            meta["flat"] = parse_properties(text)
        elif fmt == "yaml":
            meta["flat"], meta["partial_parse"] = flatten_yaml(text)
    except (ValueError, configparser.Error, tomllib.TOMLDecodeError) as e:
        meta["flat"], meta["partial_parse"] = None, True
        meta["notes"].append(f"config parse failed: {e}")


def parse_properties(text):
    out, lines, i = {}, text.splitlines(), 0
    while i < len(lines):
        line = lines[i].lstrip()
        i += 1
        if not line or line[0] in "#!":
            continue
        while line.endswith("\\") and not line.endswith("\\\\") and i < len(lines):
            line = line[:-1] + lines[i].lstrip()
            i += 1
        m = re.match(r"^((?:\\.|[^\s=:\\])+)\s*(?:[=:]|\s)\s*(.*)$", line) or re.match(r"^(\S+)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip() if m.lastindex == 2 else ""
    return out


YAML_KEY = re.compile(r"""^("[^"]*"|'[^']*'|[^\s:#\-?!&*|>'"{\[][^:]*?|-[^\s:][^:]*?)\s*:(?:\s+(.*))?$""")


def strip_comment(s):
    quote = None
    for i, ch in enumerate(s):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'" and (i == 0 or s[i - 1] in " \t:-[{,"):
            quote = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
    return s.rstrip()


def yaml_scalar(v):
    """Return (value, partial) for one inline value."""
    v = v.strip()
    partial = False
    while v[:1] in ("&", "!") and " " in v:
        partial = True
        v = v.split(None, 1)[1]
    if v[:1] in ("&", "!", "*") or (v[:1] in "{[" and v not in ("[]", "{}")):
        return v, True
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    elif v in ("~", "null", "Null", "NULL"):
        v = "null"
    elif v.lower() in ("true", "false"):
        v = v.lower()
    return v, partial


def flatten_yaml(text):
    """Flatten a block-style YAML subset: mappings, lists, scalars, | and > blocks.

    Anchors, aliases, tags, flow collections and extra documents set the
    partial flag; parsing carries on with what it can read.
    """
    out, partial = {}, False
    lines = text.expandtabs(8).splitlines()
    stack = [(-1, [], "root")]            # (indent, path, kind)
    counters = {}
    docs, i = 0, 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        if raw.startswith("---"):
            docs += 1
            if docs > 1 or any(out):
                partial = True
            continue
        if raw.startswith("..."):
            continue
        line = strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip()
        item = False
        while body.startswith("- ") or body == "-":
            item = True
            while stack[-1][0] > indent or (stack[-1][0] == indent and stack[-1][2] == "item"):
                stack.pop()
            parent = stack[-1][1]
            key = tuple(parent)
            idx = counters.get(key, 0)
            counters[key] = idx + 1
            path = parent[:-1] + [f"{parent[-1]}[{idx}]"] if parent else [f"[{idx}]"]
            stack.append((indent, path, "item"))
            rest = body[1:].lstrip()
            indent += len(body) - len(rest)
            body = rest
            if not body:
                break
        if item and not body:
            continue
        if item and not YAML_KEY.match(body):
            val, p = yaml_scalar(body)
            partial |= p
            out[".".join(stack[-1][1])] = val
            continue
        m = YAML_KEY.match(body)
        if not m:
            partial = True
            continue
        while stack[-1][0] >= indent and not (item and stack[-1][2] == "item" and stack[-1][0] < indent):
            stack.pop()
        parent = stack[-1][1]
        k = m.group(1).strip()
        if k[:1] in "\"'" and k[-1:] == k[:1]:
            k = k[1:-1]
        if k == "<<":
            partial = True
            continue
        path = parent + [k]
        val = (m.group(2) or "").strip()
        if re.fullmatch(r"[&!]\S+", val):
            partial, val = True, ""
        if val in ("|", ">", "|-", ">-", "|+", ">+"):
            block = []
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) <= indent:
                    break
                block.append(nxt.strip())
                i += 1
            out[".".join(path)] = " ".join(b for b in block if b)
        elif val == "":
            stack.append((indent, path, "key"))
        else:
            v, p = yaml_scalar(val)
            partial |= p
            out[".".join(path)] = v
    return out, partial


# --- corpus view -----------------------------------------------------------------

class Corpus:
    """File records plus lazily loaded text, for the analysis modules."""

    def __init__(self, records, metas, cache_dir, settings):
        self.records, self.settings = records, settings
        self.by_id = {r["id"]: r for r in records}
        self._meta, self._cache_dir = metas, Path(cache_dir)
        self._text, self._norm, self._sh = {}, {}, {}

    def meta(self, rec):
        return self._meta.get(rec["id"]) or {}

    def text(self, rec):
        if rec["id"] not in self._text:
            p = self._cache_dir / "text" / f"{rec['sha256']}.md"
            self._text[rec["id"]] = p.read_text() if p.exists() else ""
        return self._text[rec["id"]]

    def norm(self, rec):
        if rec["id"] not in self._norm:
            self._norm[rec["id"]] = normalize(self.text(rec))
        return self._norm[rec["id"]]

    def shingles(self, rec, k=5):
        key = (rec["id"], k)
        if key not in self._sh:
            self._sh[key] = shingle_set(self.norm(rec), k)
        return self._sh[key]
