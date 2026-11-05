#!/usr/bin/env python3
"""token-saver helpers: local, deterministic work so no model call is needed.

Subcommands (all print to stdout, errors to stderr, standard library only):
  search   bounded passage search over a file or directory
  count    line/word counts, or frequency of lines/fields
  fields   extract columns/keys from CSV, TSV, JSON or JSONL
  dates    normalize dates found in text to ISO 8601
  diff     compare two files (unified diff, capped)
  accept   save a result as the one current accepted result for a job
  current  print the current accepted result for a job
"""
import argparse
import csv
import difflib
import io
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "graphify-out", "dist", "build"}
STATE_ROOT = Path(os.environ.get("TOKEN_SAVER_STATE", Path.home() / ".claude" / "state" / "token-saver"))


def die(msg, code=2):
    print(f"tokensaver: {msg}", file=sys.stderr)
    sys.exit(code)


def read_text(path):
    data = Path(path).read_bytes()
    if b"\0" in data[:4096]:
        return None
    return data.decode("utf-8", errors="replace")


def iter_files(root):
    root = Path(root)
    if root.is_file():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            yield Path(dirpath) / name


# ---------------------------------------------------------------- search
def cmd_search(a):
    flags = re.IGNORECASE if a.ignore_case else 0
    pat = re.compile(re.escape(a.pattern) if a.fixed else a.pattern, flags)
    hits = []  # (path, lines, [matching line numbers])
    for f in iter_files(a.path):
        text = read_text(f)
        if text is None:
            continue
        lines = text.splitlines()
        nums = [i for i, ln in enumerate(lines) if pat.search(ln)]
        if nums:
            hits.append((f, lines, nums))
    # flatten to passages: merge overlapping context windows per file
    passages = []
    for f, lines, nums in hits:
        start = end = None
        for n in nums:
            lo, hi = max(0, n - a.context), min(len(lines), n + a.context + 1)
            if start is None:
                start, end = lo, hi
            elif lo <= end:
                end = max(end, hi)
            else:
                passages.append((f, lines, start, end))
                start, end = lo, hi
        passages.append((f, lines, start, end))
    total = len(passages)
    out, used, shown = [], 0, 0
    for f, lines, lo, hi in passages[a.skip:]:
        block = f"--- {f}:{lo + 1}-{hi}\n" + "\n".join(lines[lo:hi]) + "\n"
        if len(block) > a.max_chars:
            block = block[: a.max_chars] + "\n[passage truncated]\n"
        if used + len(block) > a.max_chars and shown:
            break
        out.append(block)
        used += len(block)
        shown += 1
    sys.stdout.write("".join(out))
    left = total - a.skip - shown
    print(f"[{total} passage(s) matched; showed {a.skip + 1}-{a.skip + shown}; {max(left, 0)} more."
          + (f" Next bounded pull: --skip {a.skip + shown}]" if left > 0 else "]"))
    if total == 0:
        sys.exit(1)


# ----------------------------------------------------------------- count
def cmd_count(a):
    text = sys.stdin.read() if a.file == "-" else (read_text(a.file) or die("binary file"))
    lines = text.splitlines()
    if a.by == "lines":
        print(f"lines={len(lines)} words={len(text.split())} chars={len(text)}")
        return
    if a.by == "unique":
        c = Counter(lines)
    else:  # field
        c = Counter()
        for row in csv.reader(io.StringIO(text), delimiter=a.delimiter):
            if a.field < len(row):
                c[row[a.field].strip()] += 1
    for k, v in c.most_common(a.top):
        print(f"{v}\t{k}")


# ---------------------------------------------------------------- fields
def cmd_fields(a):
    text = sys.stdin.read() if a.file == "-" else (read_text(a.file) or die("binary file"))
    names = [n.strip() for n in a.names.split(",")]
    fmt = a.format
    if fmt == "auto":
        ext = Path(a.file).suffix.lower()
        fmt = {".csv": "csv", ".tsv": "tsv", ".json": "json", ".jsonl": "jsonl"}.get(ext)
        if fmt is None:
            fmt = "jsonl" if text.lstrip().startswith("{") and "\n{" in text else "json" if text.lstrip()[:1] in "[{" else "csv"
    if fmt in ("csv", "tsv"):
        rows = csv.DictReader(io.StringIO(text), delimiter="\t" if fmt == "tsv" else ",")
        missing = [n for n in names if n not in (rows.fieldnames or [])]
        if missing:
            die(f"no such column(s): {missing}; have {rows.fieldnames}")
        records = list(rows)
    else:
        if fmt == "jsonl":
            records = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
        else:
            data = json.loads(text)
            records = data if isinstance(data, list) else [data]

    def dig(rec, dotted):
        for part in dotted.split("."):
            rec = rec.get(part) if isinstance(rec, dict) else None
        return rec

    w = csv.writer(sys.stdout, delimiter="\t", lineterminator="\n")
    w.writerow(names)
    for r in records:
        w.writerow(["" if (v := dig(r, n)) is None else v for n in names])


# ----------------------------------------------------------------- dates
DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y",
    "%B %d %Y", "%b %d %Y", "%m/%d/%Y", "%d.%m.%Y", "%Y%m%d",
]
DATE_RE = re.compile(
    r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[/.]\d{1,2}[/.]\d{4}|\d{8}|"
    r"\d{1,2} [A-Za-z]{3,9} \d{4}|[A-Za-z]{3,9} \d{1,2},? \d{4})\b"
)


def norm_date(s, dayfirst):
    s = s.strip()
    fmts = list(DATE_FORMATS)
    if dayfirst:
        fmts.remove("%m/%d/%Y")
        fmts.insert(0, "%d/%m/%Y")
    for f in fmts:
        try:
            return datetime.strptime(s, f).date().isoformat()
        except ValueError:
            continue
    return None


def cmd_dates(a):
    text = sys.stdin.read() if a.file == "-" else (read_text(a.file) or die("binary file"))
    for m in DATE_RE.finditer(text):
        iso = norm_date(m.group(1), a.dayfirst)
        print(f"{m.group(1)}\t{iso or 'UNPARSED'}")


# ------------------------------------------------------------------ diff
def cmd_diff(a):
    ta, tb = read_text(a.a), read_text(a.b)
    if ta is None or tb is None:
        die("binary file")
    if ta == tb:
        print("identical")
        return
    d = list(difflib.unified_diff(ta.splitlines(), tb.splitlines(), a.a, a.b, lineterm="", n=a.context))
    out = "\n".join(d)
    if len(out) > a.max_chars:
        out = out[: a.max_chars] + f"\n[diff truncated; {len(d)} diff lines total]"
    print(out)
    sys.exit(1)


# ------------------------------------------------------- accepted result
def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:60] or die("empty slug")


def cmd_accept(a):
    src = sys.stdin.read() if a.file == "-" else Path(a.file).read_text()
    d = STATE_ROOT / slugify(a.slug)
    d.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d)
    with os.fdopen(fd, "w") as fh:
        fh.write(src)
    os.replace(tmp, d / "accepted.md")  # exactly one file; overwrite, never append
    print(d / "accepted.md")


def cmd_current(a):
    p = STATE_ROOT / slugify(a.slug) / "accepted.md"
    if not p.exists():
        die(f"no accepted result for {a.slug!r}", 1)
    sys.stdout.write(p.read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search")
    s.add_argument("path")
    s.add_argument("pattern")
    s.add_argument("-C", "--context", type=int, default=2)
    s.add_argument("--max-chars", type=int, default=6000)
    s.add_argument("--skip", type=int, default=0, help="skip the first N passages (next bounded pull)")
    s.add_argument("-F", "--fixed", action="store_true")
    s.add_argument("-i", "--ignore-case", action="store_true")
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("count")
    s.add_argument("file")
    s.add_argument("--by", choices=["lines", "unique", "field"], default="lines")
    s.add_argument("--field", type=int, default=0)
    s.add_argument("--delimiter", default=",")
    s.add_argument("--top", type=int, default=20)
    s.set_defaults(fn=cmd_count)

    s = sub.add_parser("fields")
    s.add_argument("file")
    s.add_argument("names", help="comma-separated columns or dotted JSON keys")
    s.add_argument("--format", choices=["auto", "csv", "tsv", "json", "jsonl"], default="auto")
    s.set_defaults(fn=cmd_fields)

    s = sub.add_parser("dates")
    s.add_argument("file")
    s.add_argument("--dayfirst", action="store_true")
    s.set_defaults(fn=cmd_dates)

    s = sub.add_parser("diff")
    s.add_argument("a")
    s.add_argument("b")
    s.add_argument("-C", "--context", type=int, default=2)
    s.add_argument("--max-chars", type=int, default=6000)
    s.set_defaults(fn=cmd_diff)

    s = sub.add_parser("accept")
    s.add_argument("slug")
    s.add_argument("file", help="path, or - for stdin")
    s.set_defaults(fn=cmd_accept)

    s = sub.add_parser("current")
    s.add_argument("slug")
    s.set_defaults(fn=cmd_current)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
