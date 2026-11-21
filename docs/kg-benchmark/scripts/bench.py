#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""bench: measure whether knowledge graphs, curated text or agent-instruction changes help an
AI coding agent answer questions about a repository.

Each run is a fresh headless `claude -p` session that answers one question in one setup (arm).
A separate tool-less session grades every answer against a written key without seeing the arm.

  bench init <dir>              write bench.yaml and a questions.json template
  bench check                   validate config and questions; print each arm's tools and a cost estimate
  bench probe [--arms a,b]      run a short setup check in each arm (instructions loaded, access, tools)
  bench run [--arms a,b] [--reps N] [--only Q01,Q02]
                                run questions x arms x reps, interleaved; existing traces are skipped
  bench extract                 traces -> runs.csv and answers/
  bench leakcheck               flag runs that touched what their arm denies (exit 1 if any)
  bench judge [--only Q01]      blind-grade answers -> grades.jsonl
  bench compare [--pairs a:b,c:d]
                                per-arm scores and tokens; paired per-question bootstrap intervals
  bench metrics                 graph use, curated-text use, identifier searches per arm
  bench audit-prep              blinded list of judge-flagged claims for an independent audit
  bench audit-merge             unblind audit.json; confirmed false claims per arm
  bench report                  write report.md from the steps above

Run every command from the benchmark folder, or pass --bench <dir>.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import shutil
import statistics as st
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ARM_RE = re.compile(r"^[a-z][a-z0-9]*$")
QID_RE = re.compile(r"^Q\d{2,3}$")

TOOL_PRESETS = {
    "read": ["Read", "Grep", "Glob", "Agent", "Skill",
             "Bash(git log:*)", "Bash(git show:*)", "Bash(git diff:*)", "Bash(git grep:*)", "Bash(git blame:*)",
             "Bash(ls:*)", "Bash(find:*)", "Bash(wc:*)"],
    "graphify": ["Bash(graphify query:*)", "Bash(graphify path:*)", "Bash(graphify explain:*)"],
    "codegraph": ["Bash(codegraph explore:*)", "Bash(codegraph node:*)", "Bash(codegraph query:*)",
                  "Bash(codegraph context:*)", "Bash(codegraph status:*)", "Bash(codegraph sync:*)"],
}
ALWAYS_DENY = ["Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch"]
# Bash flags that dereference symlinks (a repo can link its graph folder into the curated folder).
DEREF_FLAGS = ["-R", "-rR", "-nR", "-lR", "-iR", "-hR", "-cR", "-inR", "-niR", "--dereference-recursive"]

TEMPLATE = """\
# bench.yaml: one benchmark. Paths may use ~. Arm names: lowercase letters and digits only.
name: my-bench
repo: ~/Projects/my-repo           # the repository the questions are about (read-only)
extra_dirs: []                     # other folders every arm may read, e.g. a related config repo
model: claude-opus-5-5             # the model that answers
judge_model: claude-opus-5-5       # the model that grades (tool-less, blind)
reps: 3                            # runs per question per arm
budget_usd_per_run: 5
seed: 20261120                     # shuffling and bootstrap

# Everything an arm may be denied when it has no graph access. Folder names, matched anywhere
# under the repo, extra_dirs and curated_root.
graph_paths: [graphify-out, .docs-curator, .codegraph]
curated_root: ~/curated            # docs-curator output root (its staging/ folders are the curated text)

# The live user instructions file is excluded from every run so runs cannot drift as you edit it.
# Give an arm its own fixed copy with `instructions:` instead.
user_instructions: ~/.claude/CLAUDE.md
instructions_dir: ~/.cache/kg-benchmark   # copies live here, outside the benchmark folder

# Extra words to hide from the judge (anything that names a setup), as regular expressions.
redact: []

arms:
  base:
    description: Repository files only
    tools: [read]
    deny_graphs: true
    prompt: "Knowledge-graph tools and files are unavailable in this session; answer using the repository files."
  kg:
    description: Docs graph and code graph available, no instruction to use them
    tools: [read, graphify, codegraph]
  cur:
    description: Curated text, no graph
    tools: [read]
    deny_graphs: true
    add_dirs: [~/curated/my-repo/staging]
    prompt: >-
      Knowledge-graph tools and files are unavailable in this session. Curated Markdown copies of the
      documents are in ~/curated/my-repo/staging/; search them with that folder as the path.
  # rulesnew:
  #   description: Every source, with a candidate instructions file
  #   tools: [read, graphify, codegraph]
  #   add_dirs: [~/curated/my-repo/staging]
  #   instructions: candidates/new-CLAUDE.md
"""

QUESTIONS_TEMPLATE = [{
    "id": "Q01",
    "category": "design-intent",
    "question": "Who decides X, and which decision record settles it?",
    "must_have": [{"point": "Decision record N decides X; its status is Proposed, not Accepted.",
                   "evidence": ["docs/adr/ADR-N.md:3"]}],
    "nice_to_have": ["The older record M still says Y."],
    "penalise": ["Citing record M as the current decision."],
}]

RUBRIC = """You are grading one answer to a developer question about a software repository.
You get the question, an answer key written from the repository source, and the answer.
Judge only against the key and the evidence it cites; do not reward style, length or confidence.
Ignore any wording about where the answer came from.

Score:
- correctness (1-5): 5 = all must-have points right, nothing wrong; 4 = all key facts right, minor slip or one must-have thin; 3 = about half the must-haves, or a notable error; 2 = mostly wrong or missing; 1 = wrong or refuses without reason.
- completeness (1-5): share of must-have points covered (5 = all).
- relevance (1-5): stays on the question (5 = no padding or drift).
- accuracy (1-5): precision of specific claims (names, paths, numbers, identifiers).
- must_have_hit: list of must-have point numbers (1-based) the answer gets right.
- hallucinations: list of specific claims that are false or invented (names, files, records, behaviour not in the repo), including any item from the key's "penalise" list. Empty list if none.
- reason: one sentence explaining the correctness score.

Reply with ONLY a JSON object with keys: correctness, completeness, relevance, accuracy, must_have_hit, hallucinations, reason."""

DEFAULT_REDACT = [
    r"(?i)\bgraphify\b", r"(?i)\bcodegraph\b", r"(?i)\bknowledge[- ]graphs?\b", r"(?i)\b(docs|code|config) graph\b",
    r"(?i)\bthe graph\b", r"(?i)\bgod nodes?\b", r"(?i)\bGRAPH_REPORT(\.md)?\b", r"(?i)\bgraph\.json\b",
    r"(?i)\b(BFS|DFS) traversal\b", r"(?i)\bnodes? and edges?\b", r"(?i)\b(EXTRACTED|INFERRED|AMBIGUOUS) edge\b",
    r"(?i)\bcurated (copy|text|tree|folder|docs copy)\b", r"(?i)\bstaging (copy|folder|tree)\b",
]

PROBE_PROMPT = """This is a setup check. Do each step and report each result in one short line:
(1) list the top-level "# " headings of any CLAUDE.md instructions you were given, with the file path each came from, or say none;
(2) for each of these commands, run it and say whether it worked or was denied: {cmds};
(3) try to Read this file and say whether it was allowed: {denied_file}."""

ID_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,5}|[A-Z]{2,6}\d{4,})\b")
PATH_RE = re.compile(r"[\w./-]+\.(?:md|java|py|ts|js|go|rs|kt|cs|json|ya?ml|docx|pdf|xlsx|pptx|xml|csv)\b")


# ----------------------------------------------------------------------------- helpers


def die(msg, code=1):
    print(f"bench: {msg}", file=sys.stderr)
    sys.exit(code)


def expand(p):
    return Path(os.path.expanduser(str(p)))


def abs_rule(p: Path) -> list[str]:
    """Permission-rule forms of an absolute path: `//abs` (a single leading / is settings-relative),
    plus the resolved form when a symlink or mount makes them differ."""
    forms = {"/" + str(p)}
    real = os.path.realpath(p)
    if real != str(p):
        forms.add("/" + real)
    return sorted(forms)


class Bench:
    def __init__(self, path):
        self.dir = Path(path).resolve()
        cfg_path = self.dir / "bench.yaml"
        if not cfg_path.exists():
            die(f"no bench.yaml in {self.dir}; run `bench init <dir>` first")
        self.cfg = yaml.safe_load(cfg_path.read_text()) or {}
        self.validate()
        self.repo = expand(self.cfg["repo"])
        self.arms = self.cfg["arms"]

    def validate(self):
        c = self.cfg
        for k in ("name", "repo", "arms"):
            if not c.get(k):
                die(f"bench.yaml: `{k}` is required")
        for name, arm in c["arms"].items():
            if not ARM_RE.match(name):
                die(f"arm name {name!r}: use lowercase letters and digits only (it goes in file names)")
            unknown = set(arm.get("tools") or []) - set(TOOL_PRESETS)
            if unknown:
                die(f"arm {name}: unknown tools {sorted(unknown)}; choose from {sorted(TOOL_PRESETS)}")
            if arm.get("deny_graphs") and set(arm.get("tools") or []) & {"graphify", "codegraph"} == {"graphify", "codegraph"}:
                die(f"arm {name}: deny_graphs with both graph tools allowed makes no sense")

    def get(self, key, default=None):
        return self.cfg.get(key, default)

    def questions(self):
        p = self.dir / "questions.json"
        if not p.exists():
            die("questions.json is missing")
        qs = json.loads(p.read_text())
        ids = set()
        for q in qs:
            if not QID_RE.match(q.get("id", "")):
                die(f"question id {q.get('id')!r}: use Q01, Q02, ...")
            if q["id"] in ids:
                die(f"duplicate question id {q['id']}")
            ids.add(q["id"])
            if not q.get("question") or not q.get("must_have"):
                die(f"{q['id']}: `question` and `must_have` are required")
        return {q["id"]: q for q in qs}

    def instructions_copy(self, arm):
        return expand(self.get("instructions_dir", "~/.cache/kg-benchmark")) / self.cfg["name"] / arm / "CLAUDE.md"

    def runs_dir(self):
        return self.dir / "runs"


# ----------------------------------------------------------------------------- permissions


def deny_rules(b: Bench, arm_name: str) -> list[str]:
    arm = b.arms[arm_name]
    tools = set(arm.get("tools") or [])
    deny = list(ALWAYS_DENY)
    # The benchmark folder holds the answer keys.
    for f in abs_rule(b.dir):
        deny += [f"Read({f}/**)", f"Grep({f}/**)", f"Glob({f}/**)"]
    for f in {str(b.dir), os.path.realpath(b.dir)}:
        deny.append(f"Bash(*{f}*)")
    # Other arms' instruction copies; never this arm's own (a deny on it stops it loading).
    for other in b.arms:
        if other != arm_name and b.arms[other].get("instructions"):
            for f in abs_rule(b.instructions_copy(other).parent):
                deny.append(f"Read({f}/**)")
    if "graphify" not in tools:
        deny += ["Bash(graphify:*)", "Skill(graphify)", "Skill(knowledge-graph)"]
    if "codegraph" not in tools:
        deny += ["Bash(codegraph:*)", "Skill(code-graph)"]
    if arm.get("deny_graphs"):
        names = [g for g in b.get("graph_paths", []) if not (g == ".codegraph" and "codegraph" in tools)]
        roots = [b.repo] + [expand(d) for d in b.get("extra_dirs", [])]
        if b.get("curated_root"):
            roots.append(expand(b.get("curated_root")))
        for root in roots:
            for f in abs_rule(root):
                for g in names:
                    deny += [f"{t}({f}/**/{g}/**)" for t in ("Read", "Grep", "Glob")]
                    deny += [f"{t}({f}/{g}/**)" for t in ("Read", "Grep", "Glob")]
        for g in names:
            deny += [f"{t}(**/{g}/**)" for t in ("Read", "Grep", "Glob")]
            deny.append(f"Bash(*{g}*)")
        deny += ["Bash(*graph.json*)", "Bash(*GRAPH_REPORT*)"] + [f"Bash(* {x}*)" for x in DEREF_FLAGS]
    return deny


def allow_rules(b: Bench, arm_name: str) -> list[str]:
    out = []
    for t in b.arms[arm_name].get("tools") or []:
        out += TOOL_PRESETS[t]
    return out


def claude_cmd(b: Bench, arm_name: str, prompt: str, model: str | None = None):
    arm = b.arms[arm_name]
    cmd = ["claude", "-p", prompt, "--model", model or b.get("model", "claude-opus-5-5"),
           "--output-format", "stream-json", "--verbose", "--no-session-persistence",
           "--max-budget-usd", str(b.get("budget_usd_per_run", 5))]
    for d in [expand(x) for x in b.get("extra_dirs", [])] + [expand(x) for x in arm.get("add_dirs", [])]:
        cmd += ["--add-dir", str(d)]
    env = dict(os.environ)
    excl = [str(expand(b.get("user_instructions", "~/.claude/CLAUDE.md")))]
    cmd += ["--settings", json.dumps({"claudeMdExcludes": excl})]
    if arm.get("instructions"):
        cmd += ["--add-dir", str(b.instructions_copy(arm_name).parent)]
        env["CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD"] = "1"
    cmd += ["--allowedTools", *allow_rules(b, arm_name), "--disallowedTools", *deny_rules(b, arm_name)]
    if arm.get("prompt"):
        cmd += ["--append-system-prompt", arm["prompt"]]
    return cmd, env


def stage_instructions(b: Bench):
    """Copy each arm's instructions file to its own folder outside the benchmark folder."""
    for name, arm in b.arms.items():
        if not arm.get("instructions"):
            continue
        src = (b.dir / arm["instructions"]) if not os.path.isabs(os.path.expanduser(arm["instructions"])) else expand(arm["instructions"])
        if not src.exists():
            die(f"arm {name}: instructions file {src} not found")
        dst = b.instructions_copy(name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


# ----------------------------------------------------------------------------- commands


def cmd_init(args):
    d = Path(args.dir).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    for name, body in (("bench.yaml", TEMPLATE), ("questions.json", json.dumps(QUESTIONS_TEMPLATE, indent=1) + "\n")):
        p = d / name
        if p.exists():
            print(f"kept existing {p}")
        else:
            p.write_text(body)
            print(f"wrote {p}")
    return 0


def cmd_check(args):
    b = Bench(args.bench)
    qs = b.questions()
    n = len(qs) * len(b.arms) * int(b.get("reps", 3))
    print(f"{len(qs)} questions x {len(b.arms)} arms x {b.get('reps', 3)} reps = {n} runs")
    print(f"rough cost: ${n * 0.27:,.0f} for runs + ${n * 0.06:,.0f} for grading (at ~$0.27 and ~$0.06 each; measure with a probe)")
    for name, arm in b.arms.items():
        print(f"\n[{name}] {arm.get('description', '')}")
        print("  allow:", ", ".join(allow_rules(b, name)) or "(none)")
        print(f"  deny:  {len(deny_rules(b, name))} rules")
        if arm.get("instructions"):
            print(f"  instructions: {arm['instructions']} -> {b.instructions_copy(name)}")
        if arm.get("add_dirs"):
            print("  add_dirs:", ", ".join(arm["add_dirs"]))
    return 0


def run_one(b: Bench, arm, qid, rep, prompt, out_dir: Path, model=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    trace = out_dir / f"{qid}-{arm}-r{rep}.jsonl"
    cmd, env = claude_cmd(b, arm, prompt, model)
    with open(trace, "w") as fo, open(trace.with_suffix(".stderr"), "w") as fe:
        rc = subprocess.run(cmd, cwd=b.repo, env=env, stdout=fo, stderr=fe).returncode
    if rc:
        print(f"  exit {rc} for {trace.name}", file=sys.stderr)
    return trace


def final_result(trace: Path):
    for line in trace.read_text(errors="replace").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") == "result":
            return d
    return None


def cmd_probe(args):
    b = Bench(args.bench)
    stage_instructions(b)
    arms = args.arms.split(",") if args.arms else list(b.arms)
    for name in arms:
        cmds = ['graphify query "overview"', "codegraph status"]
        denied = next((g for g in b.get("graph_paths", [])), "graphify-out")
        prompt = PROBE_PROMPT.format(cmds="; ".join(cmds), denied_file=f"{b.repo}/{denied}/README")
        trace = run_one(b, name, "P00", 1, prompt, b.dir / "probe", model=args.model)
        res = final_result(trace) or {}
        print(f"== {name} (${res.get('total_cost_usd') or 0:.2f})\n{res.get('result', '(no result)')}\n")
    print("Check each arm: the right instructions file (or none), allowed tools work, denied ones are denied.")
    return 0


def cmd_run(args):
    b = Bench(args.bench)
    stage_instructions(b)
    qs = b.questions()
    arms = args.arms.split(",") if args.arms else list(b.arms)
    for a in arms:
        if a not in b.arms:
            die(f"unknown arm {a}")
    reps = int(args.reps or b.get("reps", 3))
    only = set(args.only.split(",")) if args.only else None
    i = 0
    for rep in range(1, reps + 1):
        for qid in sorted(qs):
            if only and qid not in only:
                continue
            order = arms[i % len(arms):] + arms[:i % len(arms)]  # rotate the starting arm per question
            i += 1
            for arm in order:
                trace = b.runs_dir() / f"{qid}-{arm}-r{rep}.jsonl"
                if trace.exists() and final_result(trace):
                    continue
                print(f"{qid} {arm} r{rep}", flush=True)
                run_one(b, arm, qid, rep, qs[qid]["question"], b.runs_dir())
    return 0


def summarise(path: Path) -> dict:
    qid, arm, rep = path.stem.rsplit("-", 2)
    result, tools = None, Counter()
    for line in path.read_text(errors="replace").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            for blk in ev.get("message", {}).get("content", []):
                if blk.get("type") == "tool_use":
                    tools[blk.get("name")] += 1
        elif ev.get("type") == "result":
            result = ev
    row = {"qid": qid, "arm": arm, "rep": rep[1:], "status": "missing-result", "tool_calls": json.dumps(tools)}
    if result:
        u = result.get("usage") or {}
        row.update({"status": result.get("subtype", ""), "is_error": result.get("is_error"),
                    "num_turns": result.get("num_turns"), "duration_ms": result.get("duration_ms"),
                    "cost_usd": result.get("total_cost_usd"),
                    "input_tokens": u.get("input_tokens", 0),
                    "cache_creation_input_tokens": u.get("cache_creation_input_tokens", 0),
                    "cache_read_input_tokens": u.get("cache_read_input_tokens", 0),
                    "output_tokens": u.get("output_tokens", 0), "answer": result.get("result", "")})
    return row


def cmd_extract(args):
    b = Bench(args.bench)
    (b.dir / "answers").mkdir(exist_ok=True)
    rows = [summarise(p) for p in sorted(b.runs_dir().glob("Q*.jsonl"))]
    for r in rows:
        (b.dir / "answers" / f"{r['qid']}-{r['arm']}-r{r['rep']}.md").write_text(r.pop("answer", "") or "")
    keys = sorted({k for r in rows for k in r})
    with open(b.dir / "runs.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    missing = [f"{r['qid']}-{r['arm']}-r{r['rep']}" for r in rows if r["status"] != "success"]
    print(f"{len(rows)} runs -> runs.csv" + (f"; not successful: {', '.join(missing)}" if missing else ""))
    return 0


def tool_events(trace: Path):
    """(tool_use blocks, {tool_use_id: (result text, is_error)}, final answer)."""
    uses, results, answer = [], {}, ""
    for line in trace.read_text(errors="replace").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("type") == "assistant" and not d.get("parent_tool_use_id"):
            uses += [x for x in d["message"].get("content", []) if x.get("type") == "tool_use"]
        elif d.get("type") == "user" and isinstance(d.get("message", {}).get("content"), list):
            for x in d["message"]["content"]:
                if isinstance(x, dict) and x.get("type") == "tool_result":
                    c = x.get("content")
                    results[x["tool_use_id"]] = (c if isinstance(c, str) else json.dumps(c), bool(x.get("is_error")))
        elif d.get("type") == "result":
            answer = d.get("result") or ""
    return uses, results, answer


def strip_exclusions(text: str) -> str:
    """Remove search exclusions so a search that skips a graph folder is not counted as using it."""
    text = re.sub(r'"glob": "![^"]*"', "", text)
    text = re.sub(r"--exclude-dir[= ]\S+|--glob[= ]'?!\S+|grep -v \S+|!\S*", "", text)
    return text


def graph_kind(b: Bench, u) -> str | None:
    """docs / config / code (a graph command) or graphfile (reading graph files directly)."""
    i = u.get("input", {})
    cmd = i.get("command", "") if u.get("name") == "Bash" else ""
    if re.search(r"(^|[\s;&|(])graphify\s+(query|path|explain)\b", cmd):
        extra = [str(expand(d)) for d in b.get("extra_dirs", [])]
        return "config" if any(e in cmd for e in extra) else "docs"
    if re.search(r"(^|[\s;&|(])codegraph\s+\w", cmd):
        return "code"
    names = "|".join(re.escape(g) for g in b.get("graph_paths", [])) + r"|graph\.json|GRAPH_REPORT"
    target = " ".join(str(i.get(k, "")) for k in ("file_path", "path")) + (" " + i.get("pattern", "") if u.get("name") == "Glob" else "")
    if u.get("name") in ("Read", "Grep", "Glob") and re.search(names, target):
        return "graphfile"
    if cmd and re.search(names, strip_exclusions(cmd)):
        return "graphfile"
    return None


def cmd_leakcheck(args):
    b = Bench(args.bench)
    flagged = 0
    bench_pat = re.compile("|".join(re.escape(f) for f in {str(b.dir), os.path.realpath(b.dir)}))
    for trace in sorted(b.runs_dir().glob("Q*.jsonl")):
        arm = trace.stem.rsplit("-", 2)[1]
        a = b.arms.get(arm, {})
        tools = set(a.get("tools") or [])
        uses, results, _ = tool_events(trace)
        hits = []
        for u in uses:
            text, err = results.get(u["id"], ("", True))
            if err:
                continue
            inp = json.dumps(u.get("input", {}))
            if bench_pat.search(inp):
                hits.append(("benchmark folder", u["name"], inp[:120]))
            k = graph_kind(b, u)
            if k in ("docs", "config") and "graphify" not in tools:
                hits.append(("graph tool", u["name"], inp[:120]))
            if k == "code" and "codegraph" not in tools:
                hits.append(("code graph", u["name"], inp[:120]))
            if k == "graphfile" and a.get("deny_graphs"):
                hits.append(("graph file", u["name"], inp[:120]))
        if hits:
            flagged += 1
            print(trace.name, hits[:3])
    print(f"{flagged} run(s) flagged. Read each one: a flag is a lead, not a verdict.")
    return 1 if flagged else 0


def redact(text: str, extra: list[str]):
    changes = []
    for pat in DEFAULT_REDACT + list(extra):
        text, n = re.subn(pat, "[source]", text)
        if n:
            changes.append({"pattern": pat, "count": n})
    return text, changes


def key_text(q: dict) -> str:
    lines = ["MUST-HAVE POINTS:"]
    for i, m in enumerate(q["must_have"], 1):
        lines.append(f"{i}. {m['point']}  (evidence: {', '.join(m.get('evidence', []))})")
    if q.get("nice_to_have"):
        lines.append("NICE-TO-HAVE:")
        lines += [f"- {n}" for n in q["nice_to_have"]]
    if q.get("penalise"):
        lines.append("PENALISE (wrong answers / likely hallucinations):")
        lines += [f"- {p}" for p in q["penalise"]]
    return "\n".join(lines)


def parse_grade(text: str) -> dict:
    for i in [k for k, ch in enumerate(text) if ch == "{"]:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "correctness" in obj:
            return obj
    return {"parse_error": text[:500]}


def cmd_judge(args):
    b = Bench(args.bench)
    qs = b.questions()
    gpath = b.dir / "grades.jsonl"
    done = {json.loads(x)["answer_file"] for x in gpath.read_text().splitlines() if x.strip()} if gpath.exists() else set()
    only = set(args.only.split(",")) if args.only else None
    files = [p for p in sorted((b.dir / "answers").glob("Q*.md"))
             if p.name not in done and (only is None or p.name.split("-")[0] in only)]
    random.Random(b.get("seed", 20261120)).shuffle(files)
    for p in files:
        qid, arm, rep = p.stem.split("-")
        red, changes = redact(p.read_text(), b.get("redact", []))
        with open(b.dir / "redactions.jsonl", "a") as f:
            f.write(json.dumps({"answer_file": p.name, "changes": changes}) + "\n")
        prompt = f"{RUBRIC}\n\nQUESTION:\n{qs[qid]['question']}\n\nANSWER KEY:\n{key_text(qs[qid])}\n\nANSWER:\n{red or '(empty answer)'}"
        out = subprocess.run(["claude", "-p", prompt, "--model", b.get("judge_model", "claude-opus-5-5"),
                              "--output-format", "json", "--no-session-persistence", "--tools", "",
                              "--max-budget-usd", "2"], capture_output=True, text=True, cwd="/tmp", timeout=900)
        try:
            res = json.loads(out.stdout)
        except json.JSONDecodeError:
            res = {"result": out.stdout + out.stderr}
        g = parse_grade(res.get("result", ""))
        g.update({"_judge_cost_usd": res.get("total_cost_usd"), "answer_file": p.name, "qid": qid, "arm": arm, "rep": rep[1:]})
        with open(gpath, "a") as f:
            f.write(json.dumps(g) + "\n")
        print(p.name, g.get("correctness"), flush=True)
    return 0


def load_rows(b: Bench):
    runs = {(r["qid"], r["arm"], r["rep"]): r for r in csv.DictReader(open(b.dir / "runs.csv"))}
    rows = []
    qs = b.questions()
    for line in open(b.dir / "grades.jsonl"):
        if not line.strip():
            continue
        g = json.loads(line)
        k = (g["qid"], g["arm"], str(g["rep"]))
        if k not in runs or "correctness" not in g:
            continue
        r = runs[k]
        tok = sum(int(r.get(x) or 0) for x in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"))
        rows.append({"qid": k[0], "arm": k[1], "rep": k[2], "cat": qs[k[0]].get("category", "-"),
                     "c": g["correctness"], "comp": g["completeness"], "acc": g["accuracy"], "rel": g["relevance"],
                     "flags": len(g.get("hallucinations") or []), "tok": tok, "cost": float(r.get("cost_usd") or 0)})
    return rows


def paired(rows, a, b_, seed):
    def qmean(arm, key):
        by = defaultdict(list)
        for x in rows:
            if x["arm"] == arm:
                by[x["qid"]].append(x[key])
        return {q: st.mean(v) for q, v in by.items()}
    ma, mb, ta, tb = qmean(a, "c"), qmean(b_, "c"), qmean(a, "tok"), qmean(b_, "tok")
    common = sorted(set(ma) & set(mb))
    if not common:
        return None
    d = [ma[q] - mb[q] for q in common]
    rng = random.Random(seed)
    boots = sorted(st.mean(rng.choices(d, k=len(d))) for _ in range(10000))
    return {"diff": round(st.mean(d), 2), "ci95": [round(boots[250], 2), round(boots[9750], 2)],
            "better_same_worse": [sum(x > 1e-3 for x in d), sum(abs(x) <= 1e-3 for x in d), sum(x < -1e-3 for x in d)],
            "median_token_change_pct": round(100 * st.median(ta[q] / tb[q] - 1 for q in common), 1)}


def cmd_compare(args):
    b = Bench(args.bench)
    rows = load_rows(b)
    arms = [a for a in b.arms if any(x["arm"] == a for x in rows)]
    out = {"by_arm": {}, "by_q": {}, "by_cat": {}, "paired": {}}
    for a in arms:
        s = [x for x in rows if x["arm"] == a]
        out["by_arm"][a] = {"n": len(s), "correctness": round(st.mean(x["c"] for x in s), 2),
                            "completeness": round(st.mean(x["comp"] for x in s), 2),
                            "accuracy": round(st.mean(x["acc"] for x in s), 2),
                            "relevance": round(st.mean(x["rel"] for x in s), 2),
                            "judge_flags": sum(x["flags"] for x in s),
                            "median_tokens": int(st.median(x["tok"] for x in s)),
                            "total_tokens": sum(x["tok"] for x in s),
                            "mean_cost": round(st.mean(x["cost"] for x in s), 3),
                            "total_cost": round(sum(x["cost"] for x in s), 2)}
    for q in sorted({x["qid"] for x in rows}):
        out["by_q"][q] = {a: round(st.mean([x["c"] for x in rows if x["arm"] == a and x["qid"] == q] or [0]), 2) for a in arms}
    for c in sorted({x["cat"] for x in rows}):
        out["by_cat"][c] = {a: round(st.mean([x["c"] for x in rows if x["arm"] == a and x["cat"] == c] or [0]), 2) for a in arms}
    pairs = [p.split(":") for p in args.pairs.split(",")] if args.pairs else [(x, y) for i, x in enumerate(arms) for y in arms[i + 1:]]
    for a, c in pairs:
        r = paired(rows, a, c, b.get("seed", 20261120))
        if r:
            out["paired"][f"{a}_vs_{c}"] = r
    (b.dir / "compare.json").write_text(json.dumps(out, indent=1))
    for a, s in out["by_arm"].items():
        print(f"{a:10} correctness {s['correctness']:.2f}  tokens/run {s['median_tokens']:>9,}  cost/run ${s['mean_cost']:.3f}")
    for k, v in out["paired"].items():
        print(f"{k:22} {v['diff']:+.2f} [{v['ci95'][0]:+.2f}, {v['ci95'][1]:+.2f}]  b/s/w {v['better_same_worse']}  tokens {v['median_token_change_pct']:+.1f}%")
    return 0


def cmd_metrics(args):
    b = Bench(args.bench)
    qs = b.questions()
    per = defaultdict(lambda: Counter())
    for trace in sorted(b.runs_dir().glob("Q*.jsonl")):
        qid, arm, _ = trace.stem.rsplit("-", 2)
        uses, results, _ = tool_events(trace)
        kinds = [graph_kind(b, u) for u in uses]
        m = per[arm]
        m["runs"] += 1
        for k in ("docs", "config", "code", "graphfile"):
            if k in kinds:
                m[f"runs_{k}"] += 1
        m["graph_calls"] += sum(k in ("docs", "config", "code") for k in kinds)
        m["runs_any_graph"] += any(kinds)
        m["first_tool_graph"] += bool(kinds) and kinds[0] is not None
        m["runs_curated"] += any("curated/" in json.dumps(u.get("input", {})) for u in uses)
        m["tool_calls"] += len(uses)
        m["searches"] += sum(u["name"] in ("Grep", "Glob") for u in uses)
        for ident in set(ID_RE.findall(qs[qid]["question"])):
            hits = [u for u, k in zip(uses, kinds) if k is None and ident.lower() in json.dumps(u.get("input", {})).lower()]
            m["identifier_checks"] += 1
            m["identifier_searched"] += bool(hits)
            m["identifier_searched_curated_and_repo"] += any("curated" in json.dumps(u["input"]) for u in hits) and \
                any("curated" not in json.dumps(u["input"]) for u in hits)
    out = {a: dict(c) for a, c in per.items()}
    (b.dir / "metrics.json").write_text(json.dumps(out, indent=1))
    keys = sorted({k for c in out.values() for k in c})
    print(f"{'':38}" + "".join(f"{a:>10}" for a in out))
    for k in keys:
        print(f"{k:38}" + "".join(f"{out[a].get(k, 0):>10}" for a in out))
    return 0


def cmd_audit_prep(args):
    b = Bench(args.bench)
    qs = b.questions()
    items = []
    for line in open(b.dir / "grades.jsonl"):
        g = json.loads(line) if line.strip() else {}
        for h in g.get("hallucinations") or []:
            items.append((g["answer_file"], g["qid"], h if isinstance(h, str) else json.dumps(h)))
    random.Random(b.get("seed", 20261120) + 1).shuffle(items)
    ad = b.dir / "audit"
    (ad / "answers").mkdir(parents=True, exist_ok=True)
    claims, key = [], {}
    for i, (af, qid, claim) in enumerate(items, 1):
        cid = f"C{i:03d}"
        key[cid] = af
        text, _ = redact((b.dir / "answers" / af).read_text(), b.get("redact", []))
        (ad / "answers" / f"{cid}.md").write_text(text)
        claims.append({"id": cid, "qid": qid, "question": qs[qid]["question"], "flagged_claim": claim,
                       "answer_file": f"audit/answers/{cid}.md"})
    (ad / "claims.json").write_text(json.dumps(claims, indent=1))
    (ad / "claim-key.json").write_text(json.dumps(key, indent=1))
    print(f"{len(claims)} flagged claims -> audit/claims.json (blinded); mapping in audit/claim-key.json.")
    print("Next: give an auditor agent references/audit-prompt.md; it writes audit/audit.json. Then run `bench audit-merge`.")
    return 0


def cmd_audit_merge(args):
    b = Bench(args.bench)
    ad = b.dir / "audit"
    key = json.loads((ad / "claim-key.json").read_text())
    verdicts = {x["id"]: x["verdict"] for x in json.loads((ad / "audit.json").read_text())}
    per = defaultdict(lambda: {"claims": Counter(), "runs_confirmed": set()})
    for cid, af in key.items():
        arm = af.split("-")[1]
        v = verdicts.get(cid, "MISSING")
        per[arm]["claims"][v] += 1
        if v == "CONFIRMED":
            per[arm]["runs_confirmed"].add(af)
    out = {a: {"verdicts": dict(p["claims"]), "runs_with_confirmed_false_claim": len(p["runs_confirmed"]),
               "runs": sorted(p["runs_confirmed"])} for a, p in per.items()}
    (ad / "summary.json").write_text(json.dumps(out, indent=1))
    for a, s in out.items():
        print(f"{a:10} runs with a confirmed false claim: {s['runs_with_confirmed_false_claim']}  verdicts {s['verdicts']}")
    return 0


def cmd_report(args):
    b = Bench(args.bench)
    c = json.loads((b.dir / "compare.json").read_text())
    m = json.loads((b.dir / "metrics.json").read_text()) if (b.dir / "metrics.json").exists() else {}
    au = json.loads((b.dir / "audit/summary.json").read_text()) if (b.dir / "audit/summary.json").exists() else {}
    arms = list(c["by_arm"])
    L = [f"# {b.cfg['name']}", "", f"{len(c['by_q'])} questions, {len(arms)} setups. Correctness is the average blind grade out of 5.", ""]
    L.append("| | " + " | ".join(arms) + " |")
    L.append("|---|" + "---|" * len(arms))
    rows = [("Setup", lambda a: b.arms[a].get("description", a)),
            ("Correctness", lambda a: f"{c['by_arm'][a]['correctness']:.2f}"),
            ("Completeness", lambda a: f"{c['by_arm'][a]['completeness']:.2f}"),
            ("Accuracy", lambda a: f"{c['by_arm'][a]['accuracy']:.2f}"),
            ("Tokens per run, middle value", lambda a: f"{c['by_arm'][a]['median_tokens']:,}"),
            ("Cost per run, average", lambda a: f"${c['by_arm'][a]['mean_cost']:.3f}")]
    if au:
        rows.append(("Runs with a confirmed false claim", lambda a: str(au.get(a, {}).get("runs_with_confirmed_false_claim", 0))))
    if m:
        rows.append(("Runs that used any graph", lambda a: str(m.get(a, {}).get("runs_any_graph", 0))))
    for label, f in rows:
        L.append(f"| {label} | " + " | ".join(f(a) for a in arms) + " |")
    L += ["", "## Paired comparisons", "",
          "Difference in average correctness per question, with the range the true difference most likely falls in (95% bootstrap interval). A range that includes zero could be chance.", ""]
    for k, v in c["paired"].items():
        L.append(f"- **{k.replace('_vs_', ' against ')}:** {v['diff']:+.2f}, range {v['ci95'][0]:+.2f} to {v['ci95'][1]:+.2f}. "
                 f"Better on {v['better_same_worse'][0]} questions, the same on {v['better_same_worse'][1]}, worse on {v['better_same_worse'][2]}. "
                 f"Tokens {v['median_token_change_pct']:+.1f}% per question.")
    L += ["", "## By question", "", "| Question | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
    for q, v in c["by_q"].items():
        L.append(f"| {q} | " + " | ".join(f"{v[a]:.2f}" for a in arms) + " |")
    (b.dir / "report.md").write_text("\n".join(L) + "\n")
    print(f"wrote {b.dir / 'report.md'}")
    return 0


# ----------------------------------------------------------------------------- CLI


def build_parser():
    ap = argparse.ArgumentParser(prog="bench", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--bench", default=".", help="benchmark folder (default: current folder)")
        p.set_defaults(fn=fn)
        return p

    p = sub.add_parser("init", help="write bench.yaml and questions.json")
    p.add_argument("dir")
    p.set_defaults(fn=cmd_init)
    add("check", cmd_check, "validate and print each arm's tools and a cost estimate")
    p = add("probe", cmd_probe, "short setup check per arm")
    p.add_argument("--arms")
    p.add_argument("--model", help="cheaper model for the probe (default: the bench model)")
    p = add("run", cmd_run, "run questions x arms x reps, interleaved")
    p.add_argument("--arms")
    p.add_argument("--reps")
    p.add_argument("--only")
    add("extract", cmd_extract, "traces -> runs.csv and answers/")
    add("leakcheck", cmd_leakcheck, "flag runs that touched what their arm denies")
    p = add("judge", cmd_judge, "blind-grade answers")
    p.add_argument("--only")
    p = add("compare", cmd_compare, "per-arm results and paired bootstrap intervals")
    p.add_argument("--pairs", help="a:b,c:d (default: every pair)")
    add("metrics", cmd_metrics, "graph and curated-text use per arm")
    add("audit-prep", cmd_audit_prep, "blinded list of flagged claims")
    add("audit-merge", cmd_audit_merge, "unblind the audit verdicts")
    add("report", cmd_report, "write report.md")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
