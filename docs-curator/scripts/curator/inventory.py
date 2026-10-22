"""Walk every source and describe each file: id, hash, size, dates, format."""

import fnmatch
import os
from pathlib import Path

from . import file_id, log, sha256_file
from .sources import history, tracked_files

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".tox", ".idea",
             "docs-curator-out", "graphify-out"}

ALIASES = {"markdown": "md", "yml": "yaml", "jpeg": "jpg", "htm": "html", "cfg": "ini"}
NATIVE = {"md", "txt", "yaml", "json", "png", "jpg", "gif", "webp", "svg"}
CONVERT = {"pptx", "docx", "xlsx", "pdf", "ppt", "doc", "xls", "html", "csv", "toml", "ini", "properties"}
CONFIG_FORMATS = {"json", "yaml", "toml", "ini", "properties"}
LFS_MAGIC = b"version https://git-lfs.github.com/spec/v1"


def fmt_of(rel):
    ext = Path(rel).suffix.lower().lstrip(".")
    return ALIASES.get(ext, ext)


def kind_of(fmt):
    if fmt in NATIVE:
        return "native"
    if fmt in CONVERT:
        return "convert"
    return "unhandled"


def selected(rel, source):
    def hit(pat):
        return fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(Path(rel).name, pat) or \
            (pat.startswith("**/") and fnmatch.fnmatch(rel, pat[3:])) or (pat.endswith("/") and rel.startswith(pat))
    if source.include and not any(hit(p) for p in source.include):
        return False
    return not any(hit(p) for p in source.exclude)


def list_paths(source, out_dir):
    if source.is_git:
        return sorted(tracked_files(source))
    out_real = Path(out_dir).resolve()
    rels = []
    for root, dirs, files in os.walk(source.path):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and Path(root, d).resolve() != out_real)
        for f in sorted(files):
            rels.append(str((Path(root) / f).relative_to(source.path)))
    return rels


def scan(sources, out_dir):
    """Return file records for all sources, in source then path order."""
    records = []
    for s in sources:
        last, olds = history(s) if s.is_git else ({}, {})
        count = 0
        for rel in list_paths(s, out_dir):
            if any(part in SKIP_DIRS for part in Path(rel).parts[:-1]) or not selected(rel, s):
                continue
            p = s.path / rel
            if p.is_symlink() or not p.is_file():
                continue
            st = p.stat()
            fmt = fmt_of(rel)
            with open(p, "rb") as fh:
                lfs = st.st_size < 1024 and fh.read(len(LFS_MAGIC)) == LFS_MAGIC
            records.append({
                "id": file_id(s.name, rel), "source": s.name, "rel": rel, "abs": str(p),
                "size": st.st_size, "mtime": st.st_mtime, "sha256": sha256_file(p),
                "fmt": fmt, "kind": "unhandled" if lfs else kind_of(fmt), "lfs": lfs,
                "priority": s.priority, "commit": s.commit,
                "commit_date": last.get(rel), "history": olds.get(rel, []),
            })
            count += 1
        log(f"{s.name}: {count} files" + (f" @ {s.commit[:10]}" if s.commit else ""))
    return records
