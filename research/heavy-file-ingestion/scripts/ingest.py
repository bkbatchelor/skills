#!/usr/bin/env python3
"""Convert a heavy file into chunked Markdown/CSV artifacts plus INDEX.md.

Usage: ingest.py SOURCE [--out DIR] [--force] [--max-chars N]

Output: <SOURCE dir>/_ingested/<stem>/ (falls back to
~/.cache/heavy-file-ingestion/<hash>/ when the source dir is not writable).
Prints the artifact directory on the last line.
"""
import argparse, csv, hashlib, re, shutil, subprocess, sys
from datetime import date
from pathlib import Path

MAX_CHARS = 25_000
CSV_ROWS_PER_CHUNK = 2_000
PDF_PAGES_PER_CHUNK = 20
OFFICE_LEGACY = {".doc": "docx", ".ppt": "pptx", ".xls": "xlsx", ".odt": "docx",
                 ".odp": "pptx", ".ods": "xlsx", ".rtf": "docx"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout


def need(tool, hint):
    if not shutil.which(tool):
        sys.exit(f"missing tool '{tool}'. Install: {hint}")


def out_dir_for(src, digest, override):
    if override:
        return Path(override)
    d = src.parent / "_ingested" / src.stem
    try:
        d.mkdir(parents=True, exist_ok=True)
        return d
    except OSError:
        d = Path.home() / ".cache/heavy-file-ingestion" / digest[:16]
        d.mkdir(parents=True, exist_ok=True)
        return d


def split_text(text, max_chars):
    """Split on headings, then paragraphs, keeping each piece <= max_chars."""
    parts, cur = [], ""
    blocks = re.split(r"(?m)^(?=#{1,3} )", text)
    pieces = []
    for b in blocks:
        if len(b) <= max_chars:
            pieces.append(b)
        else:
            para = ""
            for p in re.split(r"\n\s*\n", b):
                if len(para) + len(p) > max_chars and para:
                    pieces.append(para)
                    para = ""
                para += p + "\n\n"
            pieces.append(para)
    for b in pieces:
        if len(cur) + len(b) > max_chars and cur:
            parts.append(cur)
            cur = ""
        cur += b
    if cur.strip():
        parts.append(cur)
    return parts


def summarize(text, n=140):
    for line in text.splitlines():
        s = re.sub(r"[#*_`|>\-]+", " ", line).strip()
        if len(s) > 15 and not re.match(r"(page|slide) \d+$", s.lower()):
            return (s[:n] + "…") if len(s) > n else s
    return "(no extractable text)"


def write_chunks(d, prefix, parts, kind, label=""):
    rows = []
    for i, t in enumerate(parts, 1):
        name = f"{prefix}-{i:03d}.md"
        (d / name).write_text(t)
        rows.append((name, kind, len(t), summarize(t) + (f" [{label}]" if label else "")))
    return rows


def pdf(src, d, a):
    need("pdftotext", "sudo pacman -S poppler")
    pages = int(re.search(r"Pages:\s+(\d+)", run(["pdfinfo", str(src)])).group(1))
    raw = run(["pdftotext", "-layout", str(src), "-"]).split("\f")[:pages]
    raw += [""] * (pages - len(raw))
    pgs = [re.sub(r"[ \t]{3,}", "  ", re.sub(r"[ \t]+\n", "\n", p)).strip() for p in raw]
    # drop running headers/footers: lines repeated on >40% of pages
    freq = {}
    for p in pgs:
        for ln in {l.strip() for l in p.splitlines() if l.strip()}:
            freq[ln] = freq.get(ln, 0) + 1
    common = {l for l, c in freq.items() if pages >= 5 and c > pages * 0.4}
    pgs = [re.sub(r"\n{3,}", "\n\n", "\n".join(l for l in p.splitlines() if l.strip() not in common)) for p in pgs]
    warns = [f"pages with little/no text (scan or image-only, needs OCR/visual review): {e}"
             for e in [[i + 1 for i, p in enumerate(pgs) if len(p.strip()) < 30]] if e]
    if common:
        warns.append(f"removed {len(common)} repeated header/footer lines")
    rows, cur, first, last = [], "", 1, 0
    def flush():
        nonlocal cur
        if cur.strip():
            name = f"pages-{first:03d}-{last:03d}.md"
            (d / name).write_text(cur)
            rows.append((name, "text", len(cur), summarize(cur) + f" [pp. {first}-{last}]"))
        cur = ""
    for i, p in enumerate(pgs, 1):
        block = f"## Page {i}\n{p}\n\n"
        if cur and (len(cur) + len(block) > a.max_chars or i - first >= PDF_PAGES_PER_CHUNK):
            flush(); first = i
        cur += block; last = i
    flush()
    if shutil.which("pdfimages"):
        (d / "assets").mkdir(exist_ok=True)
        subprocess.run(["pdfimages", "-png", "-p", "-l", str(min(pages, 200)), str(src), str(d / "assets/img")],
                       capture_output=True)
        n = len(list((d / "assets").glob("*")))
        if n:
            warns.append(f"{n} embedded images extracted to assets/ (not described)")
        else:
            (d / "assets").rmdir()
    return f"{pages} pages", rows, "pdftotext -layout", warns


def office(src, d, a):
    need("markitdown", "uv tool install 'markitdown[pdf,pptx,docx,xlsx,xls]'")
    ext, work = src.suffix.lower(), src
    if ext in OFFICE_LEGACY:
        need("soffice", "sudo pacman -S libreoffice-fresh")
        tmp = d / "_tmp"
        tmp.mkdir(exist_ok=True)
        run(["soffice", "--headless", "--convert-to", OFFICE_LEGACY[ext], "--outdir", str(tmp), str(src)])
        work = next(tmp.glob("*." + OFFICE_LEGACY[ext]))
        ext = work.suffix.lower()
    md = run(["markitdown", str(work)])
    if (d / "_tmp").exists():
        shutil.rmtree(d / "_tmp")
    if ext == ".pptx":
        slides = re.split(r"(?m)^(?=<!-- Slide number: \d+ -->)", md)
        slides = [s for s in slides if s.strip()]
        parts, cur, count = [], "", 0
        for s in slides:
            if cur and (count >= 15 or len(cur) + len(s) > a.max_chars):
                parts.append(cur); cur, count = "", 0
            cur += s; count += 1
        if cur: parts.append(cur)
        return f"{len(slides)} slides", write_chunks(d, "slides", parts, "text"), "markitdown", []
    if ext in (".xlsx", ".xlsm"):
        sheets = re.split(r"(?m)^(?=## )", md)
        rows = []
        for i, s in enumerate([s for s in sheets if s.strip()], 1):
            name = re.match(r"## (.+)", s)
            title = re.sub(r"\W+", "_", name.group(1))[:30] if name else f"sheet{i}"
            rows += write_chunks(d, f"sheet-{i:02d}-{title}", split_text(s, a.max_chars), "table")
        return f"{len(sheets)} sheets", rows, "markitdown", ["Large sheets: prefer CSV export + profile for analysis"]
    return "document", write_chunks(d, "doc", split_text(md, a.max_chars), "text"), "markitdown", []


def csv_file(src, d, a):
    rows_out, n = [], 0
    with open(src, newline="", errors="replace") as f:
        rd = csv.reader(f)
        header = next(rd, [])
        cols = [{"nonnull": 0, "samples": [], "numeric": True} for _ in header]
        buf, part = [], 1

        def flush():
            nonlocal buf, part
            if not buf: return
            name = f"rows-{part:03d}.csv"
            with open(d / name, "w", newline="") as o:
                w = csv.writer(o); w.writerow(header); w.writerows(buf)
            rows_out.append((name, "table", (d / name).stat().st_size,
                             f"rows {n - len(buf) + 1}-{n}, cols: {', '.join(header[:6])}"))
            buf, part = [], part + 1

        for r in rd:
            n += 1; buf.append(r)
            for c, v in zip(cols, r):
                if v.strip():
                    c["nonnull"] += 1
                    if len(c["samples"]) < 3 and v not in c["samples"]: c["samples"].append(v[:40])
                    if c["numeric"]:
                        try: float(v.replace(",", ""))
                        except ValueError: c["numeric"] = False
            if len(buf) >= CSV_ROWS_PER_CHUNK: flush()
        flush()
    prof = ["# Profile", f"Rows: {n}  Columns: {len(header)}", "",
            "| column | type | non-null | samples |", "|---|---|---|---|"]
    for h, c in zip(header, cols):
        prof.append(f"| {h} | {'numeric' if c['numeric'] and c['nonnull'] else 'text'} | {c['nonnull']} | {'; '.join(c['samples'])} |")
    (d / "profile.md").write_text("\n".join(prof) + "\n")
    rows_out.insert(0, ("profile.md", "profile", (d / "profile.md").stat().st_size,
                        f"Schema, null counts and samples for {len(header)} columns / {n} rows"))
    return f"{n} rows", rows_out, "python csv", []


def text_file(src, d, a):
    t = src.read_text(errors="replace")
    return f"{len(t.splitlines())} lines", write_chunks(d, "part", split_text(t, a.max_chars), "text"), "split", []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source"); ap.add_argument("--out"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--max-chars", type=int, default=MAX_CHARS)
    a = ap.parse_args()
    src = Path(a.source).resolve()
    digest = sha256(src)
    d = out_dir_for(src, digest, a.out)
    idx = d / "INDEX.md"
    if idx.exists() and f"sha256: {digest}" in idx.read_text() and not a.force:
        print("unchanged; reusing existing ingest"); print(d); return
    for old in d.iterdir():
        shutil.rmtree(old) if old.is_dir() else old.unlink()
    ext = src.suffix.lower()
    if ext == ".pdf": size, rows, tool, warns = pdf(src, d, a)
    elif ext in (".csv", ".tsv"): size, rows, tool, warns = csv_file(src, d, a)
    elif ext in (".txt", ".md", ".log", ".json", ".jsonl"): size, rows, tool, warns = text_file(src, d, a)
    else: size, rows, tool, warns = office(src, d, a)
    lines = ["---", f"source: {src}", f"sha256: {digest}", f"bytes: {src.stat().st_size}",
             f"extent: {size}", f"converted: {date.today()}", f"tool: {tool}", "---", "",
             f"# Index: {src.name}", "",
             "> Analysis MUST read these artifacts, never the original file.", "",
             "| artifact | type | chars | ~tokens | summary |", "|---|---|---|---|---|"]
    for name, kind, n, s in rows:
        lines.append(f"| [{name}]({name}) | {kind} | {n} | {n // 4} | {s.replace('|', '/')} |")
    lines += ["", "## Warnings"] + ([f"- {w}" for w in warns] or ["- none"])
    idx.write_text("\n".join(lines) + "\n")
    print(d)


if __name__ == "__main__":
    main()
