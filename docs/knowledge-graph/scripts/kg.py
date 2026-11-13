#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""kg: the repeatable docs-graph + code-graph pipeline around docs-curator, graphify and codegraph.

Deterministic steps only. Steps that need judgment (cluster verdicts, contradiction review,
graphify's LLM extraction, approving force=True or the token cost) stay with the
knowledge-graph skill, which calls these subcommands around them.

  kg init <repo> [--codegraph]   create ~/curated/<repo>/ with kg.yaml, start its git repo
  kg preflight                   check tools, skills, versions, config, symlinks, telemetry
  kg overrides [--dry-run]       regenerate overrides.yaml from git + kg.yaml rules
  kg curate                      snapshot, overrides, docs-curator analyze/update, PHI purge,
                                 verdict carry-forward, stale-verdict archive
  kg review                      list clusters still waiting for a verdict or a re-check
  kg apply                       docs-curator apply, $HOME symlinks, keeper + PHI checks, related repos
  kg graph prepare               PHI check, snapshot, changed files, cost estimate, big-file list
  kg graph check                 classify node loss of the merged graph against the snapshot
  kg graph labels                carry community labels forward from the snapshot
  kg graph finish                PHI check on the new graph, prune backups, log the run
  kg code                        codegraph sync (any branch)
  kg status                      where the pipeline stands and what to do next
  kg restore [<timestamp>]       put a snapshot back (latest by default)
  kg all                         run every scripted step up to the next one that needs a person
  kg install-shim                write ~/.local/bin/kg

The repo is the git toplevel of the current directory unless --repo is given. Docs steps
(curate, apply, graph) run only on the branches in kg.yaml (default main, develop,
develop-*) with a clean tree; --allow-any-branch overrides and is logged.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MIN_GRAPHIFY = (0, 9, 103)
HOME = Path.home()

EXIT_FAIL = 1        # generic failure / preflight blocked
EXIT_GATE = 2        # branch / clean-tree gate refused
EXIT_REVIEW = 3      # needs a person: unexplained node loss, pending reviews, keeper problems
EXIT_PHI = 4         # PHI found where it must not be

# docs-curator decisions that put content in staging (exclude, not_ingestible, unreadable do not)
STAGED_ACTIONS = {"include", "convert"}

SNAPSHOT_FILES = [  # (label, path relative to the curated dir)
    ("graph", "graphify-out/graph.json"),
    ("graph", "graphify-out/manifest.json"),
    ("graph", "graphify-out/.graphify_build.json"),
    ("graph", "graphify-out/.graphify_labels.json"),
    ("graph", "graphify-out/cost.json"),
    ("graph", "graphify-out/GRAPH_REPORT.md"),
    ("graph", "staging/graphify-out/cache"),
    ("curator", ".docs-curator/state.json"),
    ("curator", ".docs-curator/analysis.json"),
    ("curator", ".docs-curator/work/verdicts"),
    ("curator", ".docs-curator/work/verdicts-stale"),
    ("curator", "overrides.yaml"),
]

DEFAULT_KG_YAML = """\
# kg.yaml: knowledge-graph pipeline settings for {name}. Hand-made; tracked in this folder's git repo.
# docs-curator's own settings stay in config.yaml; hand overrides in overrides.manual.yaml.
source: {source}

gating:                      # docs steps (curate, apply, graph) only; codegraph sync runs anywhere
  branches: [main, develop, "develop-*"]
  require_clean: true

# Source-relative fnmatch globs ("*" crosses "/"). Excluded from staging, their extracted text is
# purged after every analyze, and a match in staging, the text cache or graph.json stops the run.
phi_globs: []

overrides:
  tracked_only: true         # stage only git-tracked documents; everything else is excluded
  exclude_groups:            # tracked, but not documentation
    - note: "test fixture"
      globs: ["*/src/test/*", "tests/*"]
    - note: "build/tool config"
      globs: ["pom.xml", "*/pom.xml", "package.json", "*/package.json", "package-lock.json", "*/package-lock.json"]
    - note: "agent tooling (not product docs)"
      enabled: false
      globs: [".claude/*", ".github/prompts/*"]

# Excluded files whose kept_instead is also excluded, already checked and fine.
known_excluded_keepers: []

carry_forward:
  verdict_overlap: 0.8       # Jaccard overlap to copy a verdict to a re-numbered cluster
  label_agreement: 0.5       # share of labelled members that must agree to reuse a community label

graph:
  cost_cap_tokens: 1500000   # an estimate above this needs a separate explicit yes
  agent_overhead_tokens: 60000  # fixed cost per extraction agent, added to the estimate
  big_file_bytes: 400000     # changed files above either limit get their own extraction chunk
  big_file_line_chars: 20000

backups:
  keep: 3

related_repos: []
#  - name: corebridge
#    path: ~/Projects/other-repo
#    graph: ~/Projects/other-repo/graphify-out/graph.json   # read-only; never rebuilt from here
#    mapper: map_other_refs.py                              # optional, relative to this folder
"""

GITIGNORE = """\
# generated by docs-curator, graphify and kg; only hand-made inputs are tracked
staging/
.docs-curator/
graphify-out/
graphify-out.*/
backups/
.kg/
overrides.yaml
overrides.yaml.bak-*
*.bak-*
semantic-cache-backup/
corebridge-refs/
*-refs/
__pycache__/
"""


# ----------------------------------------------------------------------------- basics


def die(msg, code=EXIT_FAIL):
    print(f"kg: error: {msg}", file=sys.stderr)
    sys.exit(code)


def warn(msg):
    print(f"kg: warning: {msg}", file=sys.stderr)


def now_ts():
    return dt.datetime.now().strftime("%Y%m%dT%H%M%S")


def run(cmd, cwd=None, check=True, capture=False, env=None):
    r = subprocess.run([str(c) for c in cmd], cwd=cwd, text=True, env=env,
                       capture_output=capture)
    if check and r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip()[-800:] if capture else ""
        die(f"command failed ({r.returncode}): {' '.join(map(str, cmd))}\n{detail}")
    return r


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def load_yaml(path):
    import yaml

    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def matches(path, globs):
    return any(fnmatch.fnmatch(path, g) for g in globs)


def expand(p):
    """Expand ~ and $VARS, keep the result un-resolved (so $HOME stays $HOME)."""
    return Path(os.path.expandvars(os.path.expanduser(str(p))))


def home_form(p):
    """Write a path under $HOME with the literal $HOME prefix, whichever mount it resolves through."""
    p = Path(p)
    try:
        return HOME / p.resolve().relative_to(HOME.resolve())
    except ValueError:
        return p


def skill_dir(name):
    env = os.environ.get(f"KG_SKILL_{name.upper().replace('-', '_')}")
    return Path(env) if env else HOME / ".claude/skills" / name


def curated_root():
    return expand(os.environ.get("KG_CURATED_ROOT", "~/curated"))


# ----------------------------------------------------------------------------- context


class Ctx:
    """Resolved repo, curated folder and kg.yaml settings."""

    def __init__(self, repo_arg=None, need_config=True):
        start = Path(repo_arg).expanduser() if repo_arg else Path.cwd()
        top = git(start, "rev-parse", "--show-toplevel")
        if not top:
            die(f"{start} is not inside a git repository (pass --repo)")
        self.repo = Path(top)
        self.name = self.repo.name
        self.out = curated_root() / self.name
        self.kg_yaml = self.out / "kg.yaml"
        self.kgdir = self.out / ".kg"
        self.work = self.out / ".docs-curator"
        self.cfg = {}
        if need_config:
            if not self.kg_yaml.exists():
                die(f"{self.kg_yaml} not found; run `kg init {self.repo}` first")
            self.cfg = validate_config(load_yaml(self.kg_yaml), self.kg_yaml)
            src = expand(self.cfg["source"])
            if src.resolve() != self.repo.resolve():
                die(f"kg.yaml source {src} is not this repo ({self.repo})")

    def get(self, *keys, default=None):
        node = self.cfg
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node

    @property
    def phi_globs(self):
        return list(self.cfg.get("phi_globs") or [])

    def log(self, step, **fields):
        self.kgdir.mkdir(parents=True, exist_ok=True)
        rec = {"at": dt.datetime.now().isoformat(timespec="seconds"), "step": step,
               "branch": git(self.repo, "branch", "--show-current"),
               "head": git(self.repo, "rev-parse", "--short", "HEAD"), **fields}
        with open(self.kgdir / "runs.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


CONFIG_KEYS = {"source", "gating", "phi_globs", "overrides", "known_excluded_keepers",
               "carry_forward", "graph", "backups", "related_repos"}


def validate_config(cfg, path):
    if not isinstance(cfg, dict):
        die(f"{path} must be a mapping")
    unknown = sorted(set(cfg) - CONFIG_KEYS)
    if unknown:
        die(f"unknown keys in {path}: {', '.join(unknown)}")
    if not cfg.get("source"):
        die(f"{path}: `source` is required")
    for key in ("phi_globs", "known_excluded_keepers", "related_repos"):
        if not isinstance(cfg.get(key) or [], list):
            die(f"{path}: `{key}` must be a list")
    for g in cfg.get("overrides", {}).get("exclude_groups", []) or []:
        if not isinstance(g, dict) or not g.get("note") or not isinstance(g.get("globs"), list):
            die(f"{path}: each overrides.exclude_groups entry needs `note` and a `globs` list: {g!r}")
    for r in cfg.get("related_repos") or []:
        if not isinstance(r, dict) or not r.get("name") or not r.get("path"):
            die(f"{path}: each related_repos entry needs `name` and `path`: {r!r}")
    for k in ("verdict_overlap", "label_agreement"):
        v = (cfg.get("carry_forward") or {}).get(k)
        if v is not None and not (0 < float(v) <= 1):
            die(f"{path}: carry_forward.{k} must be in (0, 1]")
    return cfg


# ----------------------------------------------------------------------------- gating


def gate_state(ctx):
    branch = git(ctx.repo, "branch", "--show-current") or "(detached)"
    dirty = git(ctx.repo, "status", "--porcelain") or ""
    allowed = ctx.get("gating", "branches", default=["main", "develop", "develop-*"])
    ok_branch = any(fnmatch.fnmatchcase(branch, p) for p in allowed)
    need_clean = ctx.get("gating", "require_clean", default=True)
    ok = ok_branch and (not dirty or not need_clean)
    return {"branch": branch, "allowed": allowed, "ok_branch": ok_branch, "dirty": bool(dirty),
            "dirty_lines": dirty.splitlines()[:10], "ok": ok}


def gate(ctx, args, step):
    st = gate_state(ctx)
    if st["ok"]:
        return st
    why = []
    if not st["ok_branch"]:
        why.append(f"branch '{st['branch']}' is not one of {st['allowed']}")
    if st["dirty"]:
        why.append("the working tree has uncommitted or untracked changes:\n    " + "\n    ".join(st["dirty_lines"]))
    if getattr(args, "allow_any_branch", False):
        warn(f"{step}: gate overridden (--allow-any-branch): " + "; ".join(why))
        ctx.log(step, gate_override=why)
        return st
    die(f"{step} refused: " + "; ".join(why) +
        "\nThe docs graph must reflect reviewed, merged content only. Switch branch / commit, "
        "or pass --allow-any-branch if you really mean it.", EXIT_GATE)


# ----------------------------------------------------------------------------- docs-curator glue


def curate_module():
    """Import docs-curator's curate.py for its file rules, so they can never drift from a copy."""
    path = skill_dir("docs-curator") / "scripts/curate.py"
    if not path.is_file():
        die(f"docs-curator not found at {path} (install it with agentic-library)")
    spec = importlib.util.spec_from_file_location("kg_curate", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for attr in ("SUPPORTED", "SKIP_DIRS", "walk", "WORKDIR"):
        if not hasattr(mod, attr):
            die(f"{path} no longer exposes `{attr}`; kg needs it to mirror docs-curator's file walk. "
                "Update kg.py for the new docs-curator before running.")
    return mod


def curate_cmd(ctx, *args):
    dc = skill_dir("docs-curator")
    return ["uv", "run", "--no-project", "--python", "3.12", "--with-requirements", dc / "requirements.txt",
            "python", dc / "scripts/curate.py", *args, "--source", ctx.repo, "--out", ctx.out]


def run_curate(ctx, *args):
    print(f"kg: docs-curator {' '.join(args)}", flush=True)
    run(curate_cmd(ctx, *args), cwd=ctx.out)


# ----------------------------------------------------------------------------- overrides


def build_overrides(ctx, cm):
    """Return (entries, stats). entries: path -> (action, note)."""
    tracked_out = subprocess.run(["git", "-C", str(ctx.repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    tracked = {p for p in tracked_out.decode("utf-8", "surrogateescape").split("\0") if p}
    walked = [f.relative_to(ctx.repo).as_posix() for f in cm.walk(ctx.repo)
              if f.suffix.lower() in cm.SUPPORTED]
    tracked_only = ctx.get("overrides", "tracked_only", default=True)
    groups = [("PHI (kg.yaml phi_globs)", ctx.phi_globs)]
    disabled = []
    for g in ctx.get("overrides", "exclude_groups", default=[]) or []:
        (groups if g.get("enabled", True) else disabled).append((g["note"], g["globs"]))

    entries = {}
    for p in walked:
        if matches(p, ctx.phi_globs):
            entries[p] = ("exclude", "PHI (kg.yaml phi_globs)")
            continue
        if tracked_only and p not in tracked:
            entries[p] = ("exclude", "gitignored or untracked")
            continue
        for note, globs in groups[1:]:
            if matches(p, globs):
                entries[p] = ("exclude", note)
                break

    manual_path = ctx.out / "overrides.manual.yaml"
    manual = []
    if manual_path.exists():
        data = load_yaml(manual_path)
        manual = data.get("overrides", []) if isinstance(data, dict) else data
        for it in manual or []:
            if not isinstance(it, dict) or it.get("action") not in ("include", "exclude") or not it.get("path"):
                die(f"bad entry in {manual_path}: {it!r}")
            p = str(it["path"])
            if it["action"] == "include" and matches(p, ctx.phi_globs):
                die(f"{manual_path} includes {p}, which matches phi_globs; PHI can never be included")
            entries[p] = (it["action"], it.get("note", ""))
    walked_set = set(walked)
    stats = {
        "walked": len(walked),
        "tracked": len(tracked & walked_set),
        "manual": len(manual or []),
        "manual_not_found": [str(it["path"]) for it in manual or [] if str(it["path"]) not in walked_set],
        "disabled_groups": {note: sum(1 for p in walked if p in tracked and matches(p, globs))
                            for note, globs in disabled},
    }
    return entries, stats


def cmd_overrides(args, ctx=None):
    ctx = ctx or Ctx(args.repo)
    cm = curate_module()
    entries, stats = build_overrides(ctx, cm)
    from collections import Counter

    counts = Counter(note for act, note in entries.values() if act == "exclude")
    excluded = sum(1 for act, _ in entries.values() if act == "exclude")
    print(f"overrides: {stats['walked']} supported files walked, {stats['tracked']} tracked")
    for note, n in counts.most_common():
        print(f"  exclude {n:5}  {note}")
    print(f"  manual  {stats['manual']:5}  from overrides.manual.yaml"
          + (f"  (not found in tree: {stats['manual_not_found']})" if stats["manual_not_found"] else ""))
    for note, n in stats["disabled_groups"].items():
        print(f"  note: {n} files kept that the disabled group '{note}' would exclude")
    print(f"  -> about {stats['walked'] - excluded} files left for curation")
    if getattr(args, "dry_run", False):
        return
    out = ctx.out / "overrides.yaml"
    branch = git(ctx.repo, "branch", "--show-current")
    lines = [f"# GENERATED by kg overrides on {dt.datetime.now().isoformat(timespec='seconds')} from "
             f"{home_form(ctx.repo)} @ {branch}. Do not edit: change kg.yaml or overrides.manual.yaml.",
             "overrides:"]
    for p in sorted(entries):
        act, note = entries[p]
        lines += [f"  - path: {json.dumps(p)}", f"    action: {act}", f"    note: {json.dumps(note)}"]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(entries)} entries)")


# ----------------------------------------------------------------------------- PHI


def phi_shas(analysis, globs):
    """sha256 values that belong only to PHI paths (a sha shared with a non-PHI file is kept)."""
    if not analysis or not globs:
        return set()
    phi, other = set(), set()
    for f in analysis.get("files", []):
        (phi if matches(f["path"], globs) else other).add(f["sha256"])
    return phi - other


def phi_cache_files(ctx, analysis):
    shas = phi_shas(analysis, ctx.phi_globs)
    found = []
    for sha in shas:
        found += [p for p in ctx.work.glob(f"text/*/{sha}.md")]
        found += [p for p in ctx.work.glob(f"pdf/{sha}.pdf")]
    return sorted(found)


def purge_phi(ctx):
    files = phi_cache_files(ctx, read_json(ctx.work / "analysis.json"))
    for p in files:
        p.unlink()
    print(f"phi: purged {len(files)} extracted-text cache file(s) of PHI paths")
    return len(files)


def phi_scan(ctx, where=("cache", "staging", "graph")):
    """Return a list of human-readable PHI findings. Empty means clean."""
    globs = ctx.phi_globs
    if not globs:
        return []
    hits = []
    if "cache" in where:
        hits += [f"text cache: {p}" for p in phi_cache_files(ctx, read_json(ctx.work / "analysis.json"))]
    if "staging" in where:
        st = ctx.out / "staging"
        if st.is_dir():
            for f in st.rglob("*"):
                if f.is_file() and "graphify-out" not in f.relative_to(st).parts:
                    rel = f.relative_to(st).as_posix()
                    if matches(rel, globs):
                        hits.append(f"staging: {rel}")
        for d in read_jsonl_last_run(ctx.work / "decisions.jsonl"):
            if d.get("action") in STAGED_ACTIONS and matches(d.get("path", ""), globs):
                hits.append(f"decisions.jsonl: {d['path']} is {d.get('action')}")
    if "graph" in where:
        for name in ("graph.json", ".graphify_extract.json"):
            g = read_json(ctx.out / "graphify-out" / name)
            for n in (g or {}).get("nodes", []):
                sf = str(n.get("source_file") or "")
                if sf and matches(rel_to_staging(ctx, sf), globs):
                    hits.append(f"{name}: node {n.get('id')} from {sf}")
    return hits


def phi_gate(ctx, where, step):
    hits = phi_scan(ctx, where)
    if hits:
        ctx.log(step, phi_stop=len(hits))
        die(f"{step} stopped: PHI paths found ({len(hits)}):\n  " + "\n  ".join(hits[:20]) +
            ("\n  ..." if len(hits) > 20 else "") +
            "\nNothing more runs until this is fixed. `kg curate` purges the text cache; staging or graph "
            "hits mean an override or phi_globs entry is wrong.", EXIT_PHI)


def read_jsonl_last_run(path):
    p = Path(path)
    if not p.exists():
        return []
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        return []
    last = max(r.get("run_id", "") for r in rows)
    return [r for r in rows if r.get("run_id", "") == last]


def rel_to_staging(ctx, path):
    s = str(path)
    for base in {str(ctx.out / "staging"), str((ctx.out / "staging").resolve()), str(home_form(ctx.out / "staging"))}:
        if s.startswith(base + "/"):
            return s[len(base) + 1:]
    return s


# ----------------------------------------------------------------------------- snapshots


def snapshot(ctx, reason):
    ts = now_ts()
    dest = ctx.out / "backups" / ts
    n = 0
    for _, rel in SNAPSHOT_FILES:
        src = ctx.out / rel
        if not src.exists():
            continue
        tgt = dest / rel
        tgt.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, tgt, symlinks=True)
        else:
            shutil.copy2(src, tgt)
        n += 1
    write_json(dest / "SNAPSHOT.json", {"reason": reason, "at": ts, "items": n,
                                        "head": git(ctx.repo, "rev-parse", "HEAD")})
    prune_snapshots(ctx)
    print(f"snapshot: {dest} ({n} item(s), reason: {reason})")
    return dest


def snapshots(ctx):
    b = ctx.out / "backups"
    return sorted((p for p in b.iterdir() if (p / "SNAPSHOT.json").exists()), key=lambda p: p.name) if b.is_dir() else []


def prune_snapshots(ctx):
    keep = int(ctx.get("backups", "keep", default=3))
    for old in snapshots(ctx)[:-keep]:
        shutil.rmtree(old)


def cmd_restore(args):
    ctx = Ctx(args.repo)
    snaps = snapshots(ctx)
    if not snaps:
        die("no snapshots in backups/")
    snap = next((s for s in snaps if s.name == args.timestamp), None) if args.timestamp else snaps[-1]
    if not snap:
        die(f"no snapshot {args.timestamp}; have: {', '.join(s.name for s in snaps)}")
    items = [(lbl, rel) for lbl, rel in SNAPSHOT_FILES if (snap / rel).exists()
             and (args.only is None or lbl == args.only)]
    print(f"restore from {snap.name} ({read_json(snap / 'SNAPSHOT.json')['reason']}):")
    for _, rel in items:
        print(f"  {rel}")
    if not args.yes:
        print("dry run; re-run with --yes to restore these")
        return
    for _, rel in items:
        src, tgt = snap / rel, ctx.out / rel
        if tgt.is_dir() and not tgt.is_symlink():
            shutil.rmtree(tgt)
        elif tgt.exists() or tgt.is_symlink():
            tgt.unlink()
        tgt.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree(src, tgt, symlinks=True) if src.is_dir() else shutil.copy2(src, tgt))
    ctx.log("restore", snapshot=snap.name, only=args.only)
    print(f"restored {len(items)} item(s)")


# ----------------------------------------------------------------------------- verdict carry-forward


def registry_path(ctx):
    return ctx.kgdir / "clusters.json"


def register_analysis(ctx, analysis):
    """Remember every cluster's membership (path + sha) so a later re-numbered cluster can be matched."""
    if not analysis:
        return
    reg = read_json(registry_path(ctx), {})
    sha = {f["path"]: f["sha256"] for f in analysis.get("files", [])}
    for c in analysis.get("clusters", []):
        reg.setdefault(c["id"], [[m, sha.get(m)] for m in c["members"]])
    write_json(registry_path(ctx), reg)


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


def translate_paths(old_members, cur_paths, cur_by_sha):
    """Map old member paths to current ones: a missing path whose sha now lives at exactly one path moved there."""
    out, moved = [], {}
    for path, sha in old_members:
        if path in cur_paths:
            out.append(path)
        elif sha and len(cur_by_sha.get(sha, ())) == 1:
            new = cur_by_sha[sha][0]
            out.append(new)
            moved[path] = new
        else:
            out.append(path)
    return out, moved


def carry_verdict(verdict, new_id, members, moved, info):
    v = json.loads(json.dumps(verdict))
    v["cluster_id"] = new_id
    v["reviewed"] = True
    mset = set(members)
    dropped = []

    def fix(p):
        return moved.get(p, p)

    revs = []
    for r in v.get("revisions") or []:
        r["superseded"], r["superseded_by"] = fix(r.get("superseded")), fix(r.get("superseded_by"))
        (revs if r["superseded"] in mset and r["superseded_by"] in mset else dropped).append(r)
    v["revisions"] = revs
    confs = []
    for c in v.get("conflicts") or []:
        stmts = []
        for s in c.get("statements") or []:
            s["path"] = fix(s.get("path"))
            if s["path"] in mset:
                stmts.append(s)
        if len(stmts) >= 2:
            c["statements"] = stmts
            confs.append(c)
        else:
            dropped.append(c)
    v["conflicts"] = confs
    v.pop("carried_forward", None)
    v["carried_forward"] = {**info, "moved": moved, "dropped": dropped,
                            "review_done": not info["new_members"]}
    return v


def carry_forward(ctx, analysis):
    """Copy verdicts to queued clusters that are re-numbered versions of a judged cluster."""
    threshold = float(ctx.get("carry_forward", "verdict_overlap", default=0.8))
    vdir, sdir = ctx.work / "work/verdicts", ctx.work / "work/verdicts-stale"
    vdir.mkdir(parents=True, exist_ok=True)
    reg = read_json(registry_path(ctx), {})
    cur_paths = {f["path"] for f in analysis["files"]}
    cur_by_sha = {}
    for f in analysis["files"]:
        cur_by_sha.setdefault(f["sha256"], []).append(f["path"])
    clusters = {c["id"]: c for c in analysis["clusters"]}
    queued = sorted(q.stem for q in (ctx.work / "work/queue").glob("*.json"))
    pending = [q for q in queued if not (vdir / f"{q}.json").exists()]
    sources = {}
    for d in (vdir, sdir):
        for f in d.glob("*.json") if d.exists() else []:
            if f.stem in reg and f.stem not in clusters:
                sources[f.stem] = f
    carried, restored, below = [], [], []
    for q in pending:
        if (sdir / f"{q}.json").exists():  # same id re-queued (e.g. an ignored member changed)
            shutil.move(sdir / f"{q}.json", vdir / f"{q}.json")
            restored.append(q)
            continue
        members = clusters[q]["members"] if q in clusters else []
        best = (0.0, None, None, None)
        for vid, vfile in sources.items():
            old, moved = translate_paths(reg[vid], cur_paths, cur_by_sha)
            score = jaccard(old, members)
            if score > best[0]:
                best = (score, vid, vfile, (old, moved))
        score, vid, vfile, tm = best
        if vid is None:
            continue
        if score < threshold:
            below.append({"cluster": q, "best": vid, "overlap": round(score, 3)})
            continue
        old, moved = tm
        info = {"from": vid, "overlap": round(score, 4), "at": now_ts(),
                "new_members": sorted(set(members) - set(old)),
                "removed_members": sorted(set(old) - set(members))}
        verdict = read_json(vfile)
        write_json(vdir / f"{q}.json", carry_verdict(verdict, q, members, moved, info))
        carried.append(info | {"cluster": q})
    return {"carried": carried, "restored": restored, "below_threshold": below}


def overrides_excluded(ctx):
    path = ctx.out / "overrides.yaml"
    if not path.exists():
        return set()
    data = load_yaml(path)
    items = data.get("overrides", []) if isinstance(data, dict) else data
    return {str(i["path"]) for i in items or [] if i.get("action") == "exclude"}


def reopen_auto(ctx, analysis):
    """Delete auto-closed verdicts whose cluster now has two or more members that can reach staging.

    A cluster id depends only on its members, not on overrides, so including a previously excluded
    file would otherwise leave the cluster closed for good. Hand-written verdicts are never touched.
    """
    vdir = ctx.work / "work/verdicts"
    excluded = overrides_excluded(ctx)
    clusters = {c["id"]: c for c in (analysis or {}).get("clusters", [])}
    reopened = []
    for f in sorted(vdir.glob("*.json")) if vdir.exists() else []:
        v = read_json(f) or {}
        if "kg_auto" not in v or f.stem not in clusters:
            continue
        live = [m for m in clusters[f.stem]["members"] if m not in excluded and not matches(m, ctx.phi_globs)]
        if len(live) >= 2:
            f.unlink()
            reopened.append(f.stem)
    if reopened:
        print(f"verdicts: reopened {len(reopened)} auto-closed cluster(s) that now have two or more "
              f"members that can reach staging: {', '.join(reopened)}")
    return reopened


def auto_close(ctx, analysis):
    """Write a no-finding verdict for pending clusters where fewer than two members can reach staging.

    docs-curator clusters every file, including override-excluded ones; a verdict on such a cluster
    cannot change staging, so asking a person for it is wasted work. The verdict says why.
    """
    vdir = ctx.work / "work/verdicts"
    reopen_auto(ctx, analysis)
    excluded = overrides_excluded(ctx)
    clusters = {c["id"]: c for c in analysis.get("clusters", [])}
    closed = []
    for q in sorted(p.stem for p in (ctx.work / "work/queue").glob("*.json")):
        if (vdir / f"{q}.json").exists() or q not in clusters:
            continue
        live = [m for m in clusters[q]["members"] if m not in excluded and not matches(m, ctx.phi_globs)]
        if len(live) < 2:
            write_json(vdir / f"{q}.json", {"cluster_id": q, "reviewed": True,
                                            "kg_auto": f"{len(live)} member(s) can reach staging; nothing to judge"})
            closed.append(q)
    if closed:
        print(f"verdicts: auto-closed {len(closed)} cluster(s) with fewer than two members that can reach staging")
    return closed


def archive_stale(ctx):
    analysis = read_json(ctx.work / "analysis.json")
    if not analysis:
        return []
    known = {c["id"] for c in analysis["clusters"]}
    vdir, sdir = ctx.work / "work/verdicts", ctx.work / "work/verdicts-stale"
    moved = []
    for f in sorted(vdir.glob("*.json")) if vdir.exists() else []:
        if f.stem not in known:
            sdir.mkdir(parents=True, exist_ok=True)
            shutil.move(f, sdir / f.name)
            moved.append(f.stem)
    if moved:
        print(f"verdicts: archived {len(moved)} stale verdict(s) to work/verdicts-stale/")
    return moved


def review_state(ctx):
    vdir = ctx.work / "work/verdicts"
    queued = sorted(q.stem for q in (ctx.work / "work/queue").glob("*.json"))
    missing = [q for q in queued if not (vdir / f"{q}.json").exists()]
    recheck = []
    for f in sorted(vdir.glob("*.json")) if vdir.exists() else []:
        cf = (read_json(f) or {}).get("carried_forward")
        if cf and not cf.get("review_done"):
            recheck.append({"cluster": f.stem, "from": cf["from"], "overlap": cf["overlap"],
                            "new_members": cf["new_members"]})
    return {"queued": len(queued), "needs_verdict": missing, "needs_recheck": recheck}


def cmd_review(args):
    ctx = Ctx(args.repo)
    st = review_state(ctx)
    write_json(ctx.kgdir / "review.json", st)
    print(f"review: {len(st['needs_verdict'])} cluster(s) need a verdict, "
          f"{len(st['needs_recheck'])} carried verdict(s) need their new members checked")
    for q in st["needs_verdict"]:
        print(f"  verdict: work/queue/{q}.json")
    for r in st["needs_recheck"]:
        print(f"  recheck: work/verdicts/{r['cluster']}.json (from {r['from']}, overlap {r['overlap']}): "
              f"{len(r['new_members'])} new member(s)")
    print(f"details: {ctx.kgdir / 'review.json'}")
    return st


# ----------------------------------------------------------------------------- curate / apply


def cmd_curate(args, ctx=None):
    ctx = ctx or Ctx(args.repo)
    st = gate(ctx, args, "curate")
    snapshot(ctx, "before curate")
    cmd_overrides(argparse.Namespace(repo=args.repo, dry_run=False), ctx)
    register_analysis(ctx, read_json(ctx.work / "analysis.json"))
    first = not (ctx.work / "analysis.json").exists()
    run_curate(ctx, "analyze" if first else "update")
    analysis = read_json(ctx.work / "analysis.json")
    purged = purge_phi(ctx)
    register_analysis(ctx, analysis)
    cf = carry_forward(ctx, analysis)
    for c in cf["carried"]:
        print(f"verdicts: carried {c['from']} -> {c['cluster']} (overlap {c['overlap']}, "
              f"{len(c['new_members'])} new, {len(c['removed_members'])} removed member(s))")
    for c in cf["restored"]:
        print(f"verdicts: restored {c} from verdicts-stale (same cluster id re-queued)")
    for c in cf["below_threshold"]:
        print(f"verdicts: {c['cluster']} best match {c['best']} overlaps only {c['overlap']}: full review")
    closed = auto_close(ctx, analysis)
    stale = archive_stale(ctx)
    write_json(ctx.kgdir / "state.json", {**read_json(ctx.kgdir / "state.json", {}),
                                          "curated_head": git(ctx.repo, "rev-parse", "HEAD"),
                                          "curated_at": now_ts()})
    ctx.log("curate", branch_ok=st["ok"], phi_purged=purged, carried=len(cf["carried"]),
            restored=len(cf["restored"]), auto_closed=len(closed), stale_archived=len(stale))
    rs = cmd_review(args)
    if rs["needs_verdict"] or rs["needs_recheck"]:
        print("next: review the clusters above (knowledge-graph skill), then `kg apply`")
        return EXIT_REVIEW
    print("next: `kg apply`")
    return 0


def place_link(link, target):
    target = home_form(target)
    if link.is_symlink():
        cur = os.readlink(link)
        if cur == str(target):
            return f"ok        {link} -> {target}"
        if Path(cur).expanduser().resolve() == target.resolve():
            link.unlink()
            link.symlink_to(target, target_is_directory=True)
            return f"rewritten {link} -> {target} (was {cur})"
        die(f"{link} points at {cur}, not {target}; repoint it yourself if that is intended")
    if link.exists():
        die(f"{link} exists and is not a symlink; move it aside and re-run")
    link.symlink_to(target, target_is_directory=True)
    return f"created   {link} -> {target}"


def link_state(ctx):
    out = []
    for name in ("graphify-out", ".docs-curator"):
        link, target = ctx.repo / name, home_form(ctx.out / name)
        if not link.is_symlink():
            out.append((name, "missing" if not link.exists() else "not a symlink", None))
        else:
            cur = os.readlink(link)
            out.append((name, "ok" if cur == str(target) else
                        ("non-$HOME form" if Path(cur).resolve() == target.resolve() else "wrong target"), cur))
    return out


def keeper_problems(ctx):
    """Excluded files whose keeper chain (kept_instead -> kept_instead ...) ends in an excluded file.

    A duplicate whose keeper was superseded by a staged revision is fine; one whose chain ends at an
    override-excluded copy (e.g. gitignored build output) means the content silently left staging.
    """
    rows = read_jsonl_last_run(ctx.work / "decisions.jsonl")
    by = {r["path"]: r for r in rows}
    known = set(ctx.get("known_excluded_keepers", default=[]) or [])
    staged_shas = {r.get("sha256") for r in rows if r.get("action") in STAGED_ACTIONS and r.get("sha256")}
    probs = []
    for r in rows:
        if r.get("action") != "exclude" or not r.get("kept_instead") or r["path"] in known:
            continue
        if r.get("sha256") in staged_shas:  # the same bytes are staged under another path
            continue
        if matches(r["path"], ctx.phi_globs):
            continue
        seen, cur = {r["path"]}, r["kept_instead"]
        while cur in by and by[cur].get("action") == "exclude" and by[cur].get("kept_instead") and cur not in seen:
            seen.add(cur)
            cur = by[cur]["kept_instead"]
        end = by.get(cur, {})
        if end.get("action") == "exclude":
            probs.append({"path": r["path"], "reason": r.get("reason"), "kept_instead": r["kept_instead"],
                          "chain_ends": cur, "end_reason": end.get("reason")})
    return probs


def cmd_apply(args, ctx=None):
    ctx = ctx or Ctx(args.repo)
    gate(ctx, args, "apply")
    reopen_auto(ctx, read_json(ctx.work / "analysis.json"))
    rs = review_state(ctx)
    if (rs["needs_verdict"] or rs["needs_recheck"]) and not args.allow_unreviewed:
        die(f"apply refused: {len(rs['needs_verdict'])} cluster(s) without a verdict and "
            f"{len(rs['needs_recheck'])} carried verdict(s) not re-checked (`kg review`). "
            "Pass --allow-unreviewed to apply anyway (unreviewed clusters keep every member).", EXIT_REVIEW)
    archive_stale(ctx)
    run_curate(ctx, "apply")
    (ctx.out / "graphify-out").mkdir(exist_ok=True)
    for name in ("graphify-out", ".docs-curator"):
        print("link: " + place_link(ctx.repo / name, ctx.out / name))
    phi_gate(ctx, ("cache", "staging"), "apply")
    probs = keeper_problems(ctx)
    for p in probs:
        print(f"keeper: {p['path']} excluded ({p['reason']}); its keeper chain ends at {p['chain_ends']}, "
              f"which is excluded too ({p['end_reason']})")
    if probs:
        print("  fix with an include in overrides.manual.yaml, or list the path in kg.yaml known_excluded_keepers")
    for r in ctx.get("related_repos", default=[]) or []:
        run_mapper(ctx, r, skip=args.skip_related)
    ctx.log("apply", keeper_problems=len(probs))
    if probs:
        return EXIT_REVIEW
    print("next: `kg graph prepare`, then ask the user before running graphify")
    return 0


def run_mapper(ctx, repo, skip=False):
    if not repo.get("mapper"):
        return
    script = ctx.out / repo["mapper"]
    if skip:
        print(f"related: skipped {repo['name']} mapper (--skip-related)")
        return
    if not script.is_file():
        warn(f"related repo {repo['name']}: mapper {script} not found")
        return
    rpath = expand(repo["path"])
    if not rpath.is_dir():
        warn(f"related repo {repo['name']}: {rpath} not found; mapper skipped")
        return
    env = {**os.environ, "KG_SOURCE": str(ctx.repo), "KG_RELATED_NAME": repo["name"],
           "KG_RELATED_PATH": str(rpath), "KG_OUT": str(ctx.out)}
    print(f"related: running {script.name} for {repo['name']} (read-only on both repos)")
    run([sys.executable, "-I", script], cwd=ctx.out, env=env)


# ----------------------------------------------------------------------------- graph


def graphify_python(ctx):
    p = ctx.out / "graphify-out/.graphify_python"
    if p.exists():
        py = Path(p.read_text(encoding="utf-8").strip())
        if py.exists():
            return py
    exe = shutil.which("graphify")
    if exe:
        cand = Path(os.path.realpath(exe)).parent / "python"
        if cand.exists():
            return cand
    die("cannot find graphify's Python (graphify-out/.graphify_python or the graphify tool env)")


DETECT_SNIPPET = r"""
import json, sys
from pathlib import Path
from graphify.detect import detect_incremental
from graphify.paths import out_path
from graphify.watch import _read_build_excludes, _read_build_gitignore
r = detect_incremental(Path(sys.argv[1]), extra_excludes=_read_build_excludes(out_path()),
                       gitignore=_read_build_gitignore(out_path()))
print(json.dumps({"new_files": r.get("new_files", {}), "deleted": list(r.get("deleted_files", [])),
                  "total_files": r.get("total_files"), "new_total": r.get("new_total", 0)}))
"""


def avg_tokens_per_file(cost):
    runs = [r for r in (cost or {}).get("runs", []) if r.get("files")]
    files = sum(r["files"] for r in runs)
    return (sum(r.get("input_tokens", 0) for r in runs) / files) if files else None


def big_file(path, max_bytes, max_line):
    p = Path(path)
    try:
        size = p.stat().st_size
        if size > max_bytes:
            return f"{size // 1024} KB"
        with open(p, encoding="utf-8", errors="replace") as fh:
            longest = max((len(l) for l in fh), default=0)
        if longest > max_line:
            return f"lines up to {longest} chars"
    except OSError:
        return None
    return None


def fix_manifest_anchor(ctx):
    """Re-key a staging-relative graphify manifest to the anchor graphify >= 0.9.103 uses.

    graphify anchors relative manifest keys at the folder above graphify-out/ when the input is a
    subfolder of it (#3785). Here that is the curated folder, with the input at staging/, so keys
    written relative to staging/ by older versions never match and every --update re-extracts the
    whole corpus. Rewrites `k` -> `staging/k` when that is what the key names. Returns the count.
    """
    mp = ctx.out / "graphify-out/manifest.json"
    m = read_json(mp)
    if not isinstance(m, dict) or not m:
        return 0
    staging = ctx.out / "staging"
    fixed, out = 0, {}
    for k, v in m.items():
        if (not k.startswith("/") and not k.startswith("staging/")
                and (staging / k).exists() and not (ctx.out / k).exists()):
            out["staging/" + k] = v
            fixed += 1
        else:
            out[k] = v
    if fixed:
        mp.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"manifest: re-keyed {fixed} of {len(m)} entries to graphify's anchor (staging/...); "
              "without this every --update re-extracts the whole corpus")
    return fixed


def cmd_graph_prepare(args):
    ctx = Ctx(args.repo)
    gate(ctx, args, "graph prepare")
    if not (ctx.repo / "graphify-out").is_symlink():
        die("graphify-out symlink missing in the repo; run `kg apply` first")
    phi_gate(ctx, ("cache", "staging", "graph"), "graph prepare")
    snap = snapshot(ctx, "before graph")
    rekeyed = fix_manifest_anchor(ctx)
    staging = ctx.out / "staging"
    r = run([graphify_python(ctx), "-c", DETECT_SNIPPET, staging], cwd=ctx.repo, capture=True)
    det = json.loads(r.stdout.strip().splitlines()[-1])
    changed = sorted({f for fl in det["new_files"].values() for f in fl})
    rel_changed = [rel_to_staging(ctx, f) for f in changed]
    rel_deleted = [rel_to_staging(ctx, f) for f in det["deleted"]]
    cost = read_json(ctx.out / "graphify-out/cost.json")
    per_file = avg_tokens_per_file(cost)
    # Each extraction agent costs a fixed ~60k (spec + reading graph.json to reuse IDs) however few
    # files it gets; the per-file average hides that on small runs. Chunks follow graphify's ~22 files.
    overhead = int(ctx.get("graph", "agent_overhead_tokens", default=60_000))
    chunks = -(-len(changed) // 22) if changed else 0
    estimate = int((per_file or 0) * len(changed) + overhead * chunks) if (per_file or chunks) else None
    cap = int(ctx.get("graph", "cost_cap_tokens", default=1_500_000))
    mb, ml = int(ctx.get("graph", "big_file_bytes", default=400_000)), int(ctx.get("graph", "big_file_line_chars", default=20_000))
    big = [{"path": rel_to_staging(ctx, f), "why": w} for f in changed if (w := big_file(f, mb, ml))]
    has_graph = (ctx.out / "graphify-out/graph.json").exists()
    plan = {
        "at": now_ts(), "snapshot": snap.name, "staging": str(home_form(staging)),
        "mode": "update" if has_graph else "full", "changed": rel_changed, "deleted": rel_deleted,
        "total_files": det["total_files"], "tokens_per_file": round(per_file) if per_file else None,
        "estimated_input_tokens": estimate, "estimated_chunks": chunks, "cost_cap_tokens": cap,
        "over_cap": bool(estimate and estimate > cap), "big_files": big,
        "graphify_command": f"cd {home_form(ctx.repo)} && /graphify {home_form(staging)}" + (" --update" if has_graph else ""),
    }
    write_json(ctx.kgdir / "graph-plan.json", plan)
    ctx.log("graph prepare", changed=len(changed), deleted=len(rel_deleted), estimate=estimate,
            manifest_rekeyed=rekeyed)
    print(f"graph: {len(changed)} changed, {len(rel_deleted)} deleted of {det['total_files']} staged files "
          f"({plan['mode']} run)")
    if not changed and not rel_deleted:
        print("graph: nothing changed since the last build; no graphify run needed")
        return 0
    est = (f"~{estimate:,} input tokens ({len(changed)} files x {plan['tokens_per_file'] or 0:,} avg from cost.json "
           f"+ {chunks} agent(s) x {overhead:,} overhead; at least 2 agents if big files need their own chunk)") if estimate else "unknown"
    print(f"cost: {est}; cap {cap:,}" + ("  ** OVER CAP: needs a separate explicit yes **" if plan["over_cap"] else ""))
    for b in big:
        print(f"big file (own chunk, parse with python3 -I, not Read): {b['path']} ({b['why']})")
    print(f"plan: {ctx.kgdir / 'graph-plan.json'}")
    print(f"next: ask the user (cost above), then run {plan['graphify_command']}; "
          "run `kg graph check` after graphify's merge step and before writing graph.json")
    return 0


def plan_or_die(ctx):
    plan = read_json(ctx.kgdir / "graph-plan.json")
    if not plan:
        die("no graph plan; run `kg graph prepare` first")
    return plan


def node_index(graph):
    return {n["id"]: n for n in (graph or {}).get("nodes", [])}


def cmd_graph_check(args):
    ctx = Ctx(args.repo)
    plan = plan_or_die(ctx)
    old = read_json(ctx.out / "backups" / plan["snapshot"] / "graphify-out/graph.json")
    if old is None:
        print("check: no earlier graph in the snapshot (first build); nothing can be lost")
        return 0
    gdir = ctx.out / "graphify-out"
    new_path = Path(args.new) if args.new else (gdir / ".graphify_extract.json" if (gdir / ".graphify_extract.json").exists() else gdir / "graph.json")
    new = read_json(new_path)
    if new is None:
        die(f"{new_path} not found")
    on, nn = node_index(old), node_index(new)
    lost = sorted(set(on) - set(nn))
    touched = set(plan["changed"]) | set(plan["deleted"])
    explained, unexplained = [], []
    for nid in lost:
        sf = rel_to_staging(ctx, on[nid].get("source_file") or "")
        (explained if sf in touched else unexplained).append({"id": nid, "source_file": sf,
                                                               "label": on[nid].get("label")})
    result = {"old_nodes": len(on), "new_nodes": len(nn), "lost": len(lost),
              "explained": len(explained), "unexplained": unexplained, "checked": str(new_path)}
    write_json(ctx.kgdir / "graph-check.json", result | {"explained_nodes": explained})
    print(f"check: {len(on)} -> {len(nn)} nodes; {len(lost)} lost: {len(explained)} from changed/deleted files, "
          f"{len(unexplained)} unexplained")
    by_file = {}
    for u in unexplained:
        by_file.setdefault(u["source_file"], []).append(u["id"])
    for f, ids in sorted(by_file.items()):
        print(f"  unexplained: {f or '(no source_file)'}: {len(ids)} node(s), e.g. {ids[0]}")
    ctx.log("graph check", lost=len(lost), unexplained=len(unexplained))
    if unexplained:
        print("needs the user: approve force=True only after they accept the unexplained losses above")
        return EXIT_REVIEW
    print("ok: every lost node comes from a changed or deleted file; force=True is safe if graphify's shrink guard trips")
    return 0


def cmd_graph_labels(args):
    ctx = Ctx(args.repo)
    plan = plan_or_die(ctx)
    gdir = ctx.out / "graphify-out"
    analysis = read_json(gdir / ".graphify_analysis.json")
    if not analysis:
        die("graphify-out/.graphify_analysis.json not found; run this after graphify's Step 4")
    old = read_json(ctx.out / "backups" / plan["snapshot"] / "graphify-out/graph.json") or {}
    old_name = {n["id"]: n.get("community_name") for n in old.get("nodes", [])
                if n.get("community_name") and not str(n.get("community_name")).startswith("Community ")}
    new_nodes = node_index(read_json(gdir / ".graphify_extract.json") or read_json(gdir / "graph.json"))
    agree = float(ctx.get("carry_forward", "label_agreement", default=0.5))
    carried, todo = {}, {}
    from collections import Counter

    for cid, members in sorted(analysis["communities"].items(), key=lambda kv: -len(kv[1])):
        votes = Counter(old_name[m] for m in members if m in old_name)
        labelled = sum(votes.values())
        if labelled and votes.most_common(1)[0][1] / labelled >= agree:
            carried[cid] = votes.most_common(1)[0][0]
        else:
            todo[cid] = [new_nodes.get(m, {}).get("label", m) for m in members[:12]]
    seen = Counter()
    for cid in sorted(carried, key=lambda c: -len(analysis["communities"][c])):
        base = carried[cid]
        seen[base] += 1
        if seen[base] > 1:
            carried[cid] = f"{base} ({seen[base]})"
    out = {"carried": carried, "needs_name": todo}
    write_json(ctx.kgdir / "labels-proposed.json", out)
    print(f"labels: carried {len(carried)} of {len(analysis['communities'])} communities; "
          f"{len(todo)} need a name (sample node labels in {ctx.kgdir / 'labels-proposed.json'})")
    ctx.log("graph labels", carried=len(carried), todo=len(todo))
    return 0


def cmd_graph_finish(args):
    ctx = Ctx(args.repo)
    phi_gate(ctx, ("graph",), "graph finish")
    g = read_json(ctx.out / "graphify-out/graph.json") or {}
    write_json(ctx.kgdir / "state.json", {**read_json(ctx.kgdir / "state.json", {}),
                                          "graphed_head": git(ctx.repo, "rev-parse", "HEAD"),
                                          "graphed_at": now_ts()})
    for name in ("graph-plan.json",):
        p = ctx.kgdir / name
        if p.exists():
            p.rename(ctx.kgdir / f"last-{name}")
    prune_snapshots(ctx)
    ctx.log("graph finish", nodes=len(g.get("nodes", [])), edges=len(g.get("links", [])))
    print(f"graph: {len(g.get('nodes', []))} nodes, {len(g.get('links', []))} edges; "
          f"query with: graphify query \"<q>\" --graph {home_form(ctx.out / 'graphify-out/graph.json')}")
    return 0


# ----------------------------------------------------------------------------- code


def codegraph_telemetry():
    if not shutil.which("codegraph"):
        return None
    r = run(["codegraph", "telemetry", "status"], check=False, capture=True)
    line = next((l for l in (r.stdout or "").splitlines() if l.strip().lower().startswith("telemetry:")), "")
    if not line:
        return "unknown"
    return "disabled" if re.search(r"\b(disabled|off)\b", line.lower()) else "enabled"


def cmd_code(args):
    ctx = Ctx(args.repo, need_config=False)
    if not shutil.which("codegraph"):
        die("codegraph is not installed (kg never installs it)")
    if codegraph_telemetry() == "enabled":
        run(["codegraph", "telemetry", "off"], capture=True)
        warn("codegraph telemetry was on again; turned it off")
    if not (ctx.repo / ".codegraph").is_dir():
        die(f"{ctx.repo} is not indexed; ask the user, then run `kg init {ctx.repo} --codegraph`", EXIT_REVIEW)
    run(["codegraph", "sync", ctx.repo])
    if (ctx.kg_yaml).exists():
        ctx.log("code sync")
    return 0


# ----------------------------------------------------------------------------- init / preflight / status


def cmd_init(args):
    repo = Path(args.path).expanduser()
    top = git(repo, "rev-parse", "--show-toplevel")
    if not top:
        die(f"{repo} is not a git repository")
    repo = Path(top)
    out = curated_root() / repo.name
    out.mkdir(parents=True, exist_ok=True)
    made = []
    kg_yaml = out / "kg.yaml"
    if not kg_yaml.exists():
        kg_yaml.write_text(DEFAULT_KG_YAML.format(name=repo.name, source=home_form(repo)), encoding="utf-8")
        made.append("kg.yaml")
    for name, body in (("config.yaml", f"# docs-curator settings for {repo.name}; keys: docs-curator's curate.py DEFAULTS\n"),
                       ("overrides.manual.yaml", "# hand-made docs-curator decisions; win over generated rules\noverrides: []\n"),
                       (".gitignore", GITIGNORE)):
        if not (out / name).exists():
            (out / name).write_text(body, encoding="utf-8")
            made.append(name)
    if not (out / ".git").exists():
        run(["git", "init", "-q", out])
        made.append(".git")
    print(f"init: {out}: " + (", ".join(made) + " created" if made else "already set up; nothing overwritten"))
    if args.codegraph:
        if (repo / ".codegraph").is_dir():
            print("codegraph: already indexed")
        elif not shutil.which("codegraph"):
            die("codegraph is not installed (kg never installs it)")
        else:
            run(["codegraph", "init", repo])
    print(f"next: edit {kg_yaml} (phi_globs, exclude groups, related repos), then `kg preflight`")
    return 0


def version_tuple(s):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", s or "")
    return tuple(int(x) for x in m.groups()) if m else None


def cmd_preflight(args):
    ctx = Ctx(args.repo, need_config=False)
    problems, notes = [], []

    def check(ok, label, fix=None, blocking=True):
        print(f"  [{'ok' if ok else ('FAIL' if blocking else 'warn')}] {label}")
        if not ok:
            (problems if blocking else notes).append(f"{label}" + (f": {fix}" if fix else ""))

    print("tools:")
    check(bool(shutil.which("uv")), "uv on PATH", "install uv")
    py = run(["uv", "python", "find", "3.12"], check=False, capture=True) if shutil.which("uv") else None
    check(bool(py and py.returncode == 0), "Python 3.12 available to uv", "uv python install 3.12")
    gv = version_tuple(run(["graphify", "--version"], check=False, capture=True).stdout) if shutil.which("graphify") else None
    check(bool(gv and gv >= MIN_GRAPHIFY), f"graphify CLI >= {'.'.join(map(str, MIN_GRAPHIFY))} (found {'.'.join(map(str, gv)) if gv else 'none'})",
          "uv tool upgrade graphifyy")
    check(bool(shutil.which("codegraph")), "codegraph on PATH", "install codegraph (kg never installs it)")
    check(bool(shutil.which("soffice")), "soffice (LibreOffice) for .pptx", blocking=False)
    check(bool(shutil.which("pdftotext")), "pdftotext (poppler) for PDFs", blocking=False)
    tel = codegraph_telemetry()
    if tel == "enabled":
        if args.fix:
            run(["codegraph", "telemetry", "off"], capture=True)
            tel = codegraph_telemetry()
        check(tel != "enabled", "codegraph telemetry off", "run `kg preflight --fix` or `codegraph telemetry off`")
    elif tel:
        check(tel == "disabled", f"codegraph telemetry off ({tel})", "check `codegraph telemetry status`",
              blocking=False)

    print("skills:")
    for s in ("docs-curator", "heavy-file-ingestion", "code-graph", "graphify"):
        check((skill_dir(s) / "SKILL.md").is_file(), f"{s} skill at {skill_dir(s)}", "install with agentic-library"
              if s != "graphify" else "graphify install --platform claude")
    gsv = skill_dir("graphify") / ".graphify_version"
    if gsv.exists() and gv:
        check(version_tuple(gsv.read_text()) == gv, f"graphify skill version matches the CLI ({gsv.read_text().strip()})",
              "graphify install --platform claude", blocking=False)
    if (skill_dir("graphify") / "SKILL.md.bak").exists():
        check(False, "no leftover graphify SKILL.md.bak", f"rm {skill_dir('graphify') / 'SKILL.md.bak'}", blocking=False)
    if (skill_dir("docs-curator") / "scripts/curate.py").is_file():
        curate_module()
        check(True, "docs-curator curate.py exposes SUPPORTED, SKIP_DIRS, walk")

    print(f"config ({ctx.out}):")
    have_cfg = ctx.kg_yaml.exists()
    check(have_cfg, "kg.yaml present", f"kg init {ctx.repo}")
    if have_cfg:
        ctx = Ctx(args.repo)
        check(True, "kg.yaml valid, source matches this repo")
        check((ctx.out / ".git").exists(), "curated folder is a git repo", f"git init {ctx.out}", blocking=False)
        if (ctx.out / ".git").exists():
            dirty = git(ctx.out, "status", "--porcelain")
            check(not dirty, "curated folder's hand-made files are committed", f"commit in {ctx.out}", blocking=False)
        check(bool(ctx.phi_globs), "phi_globs set", "list the repo's PHI folders in kg.yaml (or confirm there are none)",
              blocking=False)
        print("repo:")
        for name, state, cur in link_state(ctx):
            check(state == "ok", f"{name} symlink {state}" + (f" ({cur})" if cur and state != "ok" else ""),
                  "`kg apply` rewrites it in $HOME form", blocking=state not in ("ok", "non-$HOME form", "missing"))
        check((ctx.repo / ".codegraph").is_dir(), "codegraph index present", f"ask, then kg init {ctx.repo} --codegraph",
              blocking=False)
        st = gate_state(ctx)
        check(st["ok"], f"docs gate: branch '{st['branch']}'" + (", dirty tree" if st["dirty"] else ", clean tree"),
              "docs steps will refuse to run", blocking=False)
        leftovers = [p.name for p in list(ctx.out.glob("*.bak-*")) + list((ctx.out / "graphify-out").glob("*.bak-*"))
                     + list(ctx.out.glob("graphify-out.stale-*")) + list(ctx.out.glob("semantic-cache-backup"))]
        check(not leftovers, "no ad-hoc .bak/.stale copies", f"after the first kg snapshot, remove: {', '.join(leftovers)}",
              blocking=False)
        cache = phi_scan(ctx, ("cache",))
        check(not cache, f"no PHI in the extracted-text cache ({len(cache)} found)", "`kg curate` purges it",
              blocking=False)
        phi = phi_scan(ctx, ("staging", "graph"))
        check(not phi, f"no PHI in staging or the graph ({len(phi)} found)",
              "fix phi_globs / overrides, then kg apply; restore a snapshot if the graph has it")
    if args.install_shim:
        cmd_install_shim(args)
    print()
    for n in notes:
        print(f"warn: {n}")
    for p in problems:
        print(f"FAIL: {p}")
    print("preflight: " + ("ready" if not problems else f"{len(problems)} blocking problem(s)"))
    return EXIT_FAIL if problems else 0


SHIM = """#!/bin/sh
# kg launcher, written by `kg install-shim` (knowledge-graph skill)
exec uv run --quiet --python 3.12 --script "{script}" "$@"
"""


def cmd_install_shim(args):
    target = expand(getattr(args, "shim_path", None) or "~/.local/bin/kg")
    script = home_form(Path(__file__).resolve())
    if (skill_dir("knowledge-graph") / "scripts/kg.py").exists():
        script = skill_dir("knowledge-graph") / "scripts/kg.py"
    body = SHIM.format(script=script)
    if target.exists() and target.read_text(encoding="utf-8", errors="replace") != body:
        if "knowledge-graph skill" not in target.read_text(encoding="utf-8", errors="replace"):
            die(f"{target} exists and was not written by kg; not overwriting")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    target.chmod(0o755)
    print(f"shim: {target} -> {script}")
    return 0


def next_step(ctx):
    """What the pipeline needs next, as (who, what)."""
    st = read_json(ctx.kgdir / "state.json", {})
    head = git(ctx.repo, "rev-parse", "HEAD")
    if not (ctx.work / "analysis.json").exists() or st.get("curated_head") != head:
        return ("kg", "curate")
    rs = review_state(ctx)
    if rs["needs_verdict"] or rs["needs_recheck"]:
        return ("skill", "review clusters (kg review)")
    an_m = (ctx.work / "analysis.json").stat().st_mtime
    staged = (ctx.out / "staging").exists() and (ctx.work / "decisions.jsonl").exists() \
        and (ctx.work / "decisions.jsonl").stat().st_mtime >= an_m
    if not staged:
        return ("kg", "apply")
    if (ctx.kgdir / "graph-plan.json").exists():
        return ("skill", "graphify run in progress (plan exists): ask, run graphify, kg graph check/labels/finish")
    if st.get("graphed_head") != head:
        return ("kg", "graph prepare")
    return ("none", "up to date")


def cmd_status(args):
    ctx = Ctx(args.repo)
    st = gate_state(ctx)
    print(f"repo     {ctx.repo} [{st['branch']}{', dirty' if st['dirty'] else ''}] docs gate: {'open' if st['ok'] else 'closed'}")
    print(f"curated  {ctx.out}")
    kst = read_json(ctx.kgdir / "state.json", {})
    head = git(ctx.repo, "rev-parse", "HEAD")
    for label, key in (("curated", "curated_head"), ("graphed", "graphed_head")):
        h = kst.get(key)
        drift = "" if h == head else (f" ({len((git(ctx.repo, 'log', '--oneline', f'{h}..HEAD') or '').splitlines())} commit(s) behind)"
                                      if h else " (never by kg)")
        print(f"{label:8} {(h or '-')[:10]} at {kst.get(key.replace('head', 'at'), '-')}{drift}")
    rs = review_state(ctx)
    print(f"review   {len(rs['needs_verdict'])} need a verdict, {len(rs['needs_recheck'])} carried need a re-check")
    for name, state, cur in link_state(ctx):
        print(f"link     {name}: {state}")
    print(f"codegraph {'indexed' if (ctx.repo / '.codegraph').is_dir() else 'not indexed'}; telemetry {codegraph_telemetry()}")
    phi = phi_scan(ctx)
    print(f"phi      {'clean' if not phi else f'{len(phi)} finding(s): run kg curate / kg preflight'}")
    print(f"backups  {', '.join(s.name for s in snapshots(ctx)) or 'none'}")
    who, what = next_step(ctx)
    print(f"next     {what}" + (" (needs the knowledge-graph skill / a person)" if who == "skill" else ""))
    return 0


def cmd_all(args):
    ctx = Ctx(args.repo)
    if cmd_preflight(argparse.Namespace(repo=args.repo, fix=False, install_shim=False)) != 0:
        die("preflight failed; fix the problems above first")
    for _ in range(4):
        who, what = next_step(ctx)
        if who != "kg":
            print(f"all: stopping before '{what}'" + (" (needs a person)" if who == "skill" else ""))
            return 0 if who == "none" else EXIT_REVIEW
        if args.dry_run:
            print(f"all: would run kg {what}, then stop at the next step that needs a person")
            return 0
        if what == "curate":
            rc = cmd_curate(args, ctx)
        elif what == "apply":
            rc = cmd_apply(args, ctx)
        else:
            return cmd_graph_prepare(args)
        if rc:
            return rc
    return 0


# ----------------------------------------------------------------------------- CLI


def build_parser():
    ap = argparse.ArgumentParser(prog="kg", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, gated=False):
        p = sub.add_parser(name, help=help_, description=help_)
        p.add_argument("--repo", help="repository (default: git toplevel of the current directory)")
        if gated:
            p.add_argument("--allow-any-branch", action="store_true",
                           help="run the docs steps off the allowed branches or with a dirty tree (logged)")
        p.set_defaults(fn=fn)
        return p

    p = sub.add_parser("init", help="create ~/curated/<repo>/ with kg.yaml and start its git repo")
    p.add_argument("path")
    p.add_argument("--codegraph", action="store_true", help="also run `codegraph init` (only after the user agreed)")
    p.set_defaults(fn=cmd_init)
    p = add("preflight", cmd_preflight, "check tools, skills, config, symlinks, telemetry, PHI")
    p.add_argument("--fix", action="store_true", help="turn codegraph telemetry off if it is on")
    p.add_argument("--install-shim", action="store_true", help="also write ~/.local/bin/kg")
    p = add("overrides", cmd_overrides, "regenerate overrides.yaml")
    p.add_argument("--dry-run", action="store_true")
    add("curate", cmd_curate, "snapshot, overrides, docs-curator analyze/update, PHI purge, carry-forward", gated=True)
    add("review", cmd_review, "list clusters needing a verdict or a re-check")
    p = add("apply", cmd_apply, "docs-curator apply, symlinks, keeper and PHI checks, related repos", gated=True)
    p.add_argument("--allow-unreviewed", action="store_true")
    p.add_argument("--skip-related", action="store_true")
    g = sub.add_parser("graph", help="steps around the graphify skill's run").add_subparsers(dest="gcmd", required=True)
    for name, fn, help_ in (("prepare", cmd_graph_prepare, "PHI check, snapshot, changed files, cost estimate"),
                            ("check", cmd_graph_check, "classify node loss against the snapshot"),
                            ("labels", cmd_graph_labels, "carry community labels forward"),
                            ("finish", cmd_graph_finish, "PHI check the new graph, prune, log")):
        p = g.add_parser(name, help=help_, description=help_)
        p.add_argument("--repo")
        if name == "prepare":
            p.add_argument("--allow-any-branch", action="store_true")
        if name == "check":
            p.add_argument("--new", help="graph to compare (default .graphify_extract.json, else graph.json)")
        p.set_defaults(fn=fn)
    add("code", cmd_code, "codegraph sync (any branch)")
    add("status", cmd_status, "pipeline state and next step")
    p = add("restore", cmd_restore, "restore a snapshot (dry run unless --yes)")
    p.add_argument("timestamp", nargs="?")
    p.add_argument("--only", choices=["graph", "curator"])
    p.add_argument("--yes", action="store_true")
    p = add("all", cmd_all, "run scripted steps up to the next one that needs a person", gated=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--allow-unreviewed", action="store_true")
    p.add_argument("--skip-related", action="store_true")
    p = sub.add_parser("install-shim", help="write ~/.local/bin/kg")
    p.add_argument("--shim-path")
    p.set_defaults(fn=cmd_install_shim)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    rc = args.fn(args)
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
