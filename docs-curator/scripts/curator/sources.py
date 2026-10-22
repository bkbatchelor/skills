"""Source declarations (sources.toml or command-line paths/URLs), cloning,
and git history lookups.

Sources are read-only. The only thing written is a clone of a remote source
under <out>/sources/<name>/, which is ours.
"""

import os
import re
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import die, log, slug

GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}


@dataclass
class Source:
    name: str
    path: Path | None = None
    url: str | None = None
    ref: str | None = None
    priority: int = 0
    include: list = field(default_factory=list)
    exclude: list = field(default_factory=list)
    commit: str | None = None
    is_git: bool = False

    @property
    def location(self):
        return self.url or str(self.path)

    def public(self):
        return {"name": self.name, "location": self.location, "ref": self.ref,
                "priority": self.priority, "commit": self.commit, "is_git": self.is_git,
                "include": self.include, "exclude": self.exclude}


# --- declarations ------------------------------------------------------------

def looks_like_url(s):
    return "://" in s or re.match(r"^[\w.-]+@[\w.-]+:", s) is not None


def load_toml(path):
    path = Path(path).expanduser().resolve()
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        die(f"cannot read {path}: {e}")
    entries = data.get("source")
    if not isinstance(entries, list) or not entries:
        die(f"{path}: needs at least one [[source]] entry")
    out = []
    for i, e in enumerate(entries, 1):
        if bool(e.get("path")) == bool(e.get("url")):
            die(f"{path}: source #{i} needs exactly one of 'path' or 'url'")
        name = slug(e.get("name") or Path(e.get("path") or e["url"]).name.removesuffix(".git"))
        src = Source(name=name, ref=e.get("ref"), priority=int(e.get("priority", 0)),
                     include=list(e.get("include", [])), exclude=list(e.get("exclude", [])))
        if e.get("url"):
            src.url = e["url"]
        else:
            p = Path(e["path"]).expanduser()
            src.path = (p if p.is_absolute() else path.parent / p).resolve()
        out.append(src)
    return unique_names(out)


def from_args(items):
    out = []
    for item in items:
        if looks_like_url(item):
            out.append(Source(name=slug(item.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")), url=item))
        else:
            out.append(Source(name=slug(Path(item).expanduser().resolve().name), path=Path(item).expanduser().resolve()))
    return unique_names(out)


def unique_names(sources):
    seen = {}
    for s in sources:
        n = seen.get(s.name, 0) + 1
        seen[s.name] = n
        if n > 1:
            s.name = f"{s.name}-{n}"
    return sources


# --- git ---------------------------------------------------------------------

def git(args, cwd, check=False):
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=cwd, env=GIT_ENV,
                           capture_output=True, text=True, errors="replace")
    except FileNotFoundError:
        die("git is not installed")
    if r.returncode != 0:
        if check:
            die(f"git {' '.join(args)} failed in {cwd}: {r.stderr.strip()}")
        return None
    return r.stdout


def prepare(sources, out_dir):
    """Clone or update remote sources, then fill in is_git and commit."""
    for s in sources:
        if s.url:
            dest = Path(out_dir) / "sources" / s.name
            s.path = dest
            if (dest / ".git").is_dir():
                log(f"fetching {s.name}")
                git(["fetch", "--depth", "50", "origin", s.ref or "HEAD"], dest, check=True)
                git(["checkout", "-q", "--force", "--detach", "FETCH_HEAD"], dest, check=True)
            else:
                log(f"cloning {s.url} -> {dest}")
                dest.parent.mkdir(parents=True, exist_ok=True)
                cmd = ["clone", "-q", "--depth", "50"] + (["--branch", s.ref] if s.ref else []) + [s.url, str(dest)]
                git(cmd, dest.parent, check=True)
        elif not s.path.is_dir():
            die(f"source '{s.name}': {s.path} is not a directory")
        top = git(["rev-parse", "--show-toplevel"], s.path)
        s.is_git = top is not None
        if s.is_git:
            s.commit = (git(["rev-parse", "HEAD"], s.path) or "").strip() or None
    return sources


def tracked_files(source):
    out = git(["ls-files", "-z"], source.path)
    return [p for p in (out or "").split("\0") if p]


def history(source):
    """Last commit date per current path, and the older names of renamed files.

    Walks `git log --name-status -M` newest first, following renames
    backwards through an alias map.
    """
    last, olds, alias = {}, {}, {}
    out = git(["log", "--name-status", "-M", "--relative", "--format=@@%cI"], source.path)
    if not out:
        return last, olds
    date = None
    for line in out.splitlines():
        if line.startswith("@@"):
            date = line[2:]
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        if status[0] in "RC" and len(parts) >= 3:
            old, new = parts[1], parts[2]
            cur = alias.get(new, new)
            last.setdefault(cur, date)
            if status[0] == "R":
                alias[old] = cur
                olds.setdefault(cur, []).append(old)
        else:
            path = parts[-1]
            last.setdefault(alias.get(path, path), date)
    return last, olds
