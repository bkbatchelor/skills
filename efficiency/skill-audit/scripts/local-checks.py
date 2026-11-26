#!/usr/bin/env python3
"""Keyless local checks for skill-audit: context cost and broken references.

Usage:
  python3 -I local-checks.py [--repo DIR] [--mcp NAME,...] <skill>... | --all

<skill> is a name or a path. Prints one JSON document to stdout.
Token counts are estimates: characters divided by 4.
Exit codes: 0 ran, 2 usage error or unknown skill.
"""
import json
import os
import re
import sys

REF = re.compile(r"`((?:scripts|references|docs|styles|templates|assets)/[\w./-]+)`")
MCP = re.compile(r"mcp__([A-Za-z0-9-]+)__")


def parse_frontmatter(text):
    """Return (dict, error). Handles plain, quoted, and block (> | >- |-) scalars."""
    m = re.match(r"---\n(.*?)\n---(?:\n|$)", text, re.S)
    if not m:
        return {}, "no frontmatter"
    out, key, buf, style = {}, None, [], None

    def flush():
        if key is None:
            return
        if style in (">", ">-", ">+"):
            out[key] = " ".join(s.strip() for s in buf).strip()
        elif style in ("|", "|-", "|+"):
            out[key] = "\n".join(s.strip() for s in buf).strip()
        else:
            out[key] = " ".join(s.strip() for s in buf).strip().strip("\"'")

    for line in m.group(1).split("\n"):
        top = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if top and not line.startswith((" ", "\t")):
            flush()
            key, rest = top.group(1), top.group(2)
            style = rest if rest in (">", ">-", ">+", "|", "|-", "|+") else None
            buf = [] if style else [rest]
        elif key is not None:
            buf.append(line)
    flush()
    return out, None


def skills_in(repo):
    found = {}
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules"]
        if "SKILL.md" in files:
            found[os.path.basename(root)] = root
    return found


def check(skill_dir, repo, mcp_known):
    path = os.path.join(skill_dir, "SKILL.md")
    text = open(path, encoding="utf-8").read()
    fm, err = parse_frontmatter(text)
    name, desc = fm.get("name", ""), fm.get("description", "")
    issues = []
    if err:
        issues.append({"severity": "high", "type": "frontmatter", "detail": err})
    if len(desc) > 1024:
        issues.append({"severity": "medium", "type": "long-description",
                       "detail": f"{len(desc)} characters (limit 1024)"})
    lines = text.count("\n") + 1
    if lines > 500:
        issues.append({"severity": "medium", "type": "long-skill",
                       "detail": f"SKILL.md has {lines} lines (over 500)"})
    refs = sorted(set(REF.findall(text)))
    for r in refs:
        r = r.rstrip(".,")
        if not (os.path.exists(os.path.join(skill_dir, r)) or os.path.exists(os.path.join(repo, r))):
            issues.append({"severity": "low", "type": "missing-reference",
                           "detail": f"{r} not found under the skill or the repo "
                                     "(verify: it may be an illustrative example)"})
    if mcp_known is not None:
        for s in sorted(set(MCP.findall(text))):
            if s not in mcp_known:
                issues.append({"severity": "medium", "type": "unknown-mcp",
                               "detail": f"mcp__{s}__* is not a configured server"})
    return {
        "skill": name or os.path.basename(skill_dir),
        "path": os.path.relpath(skill_dir, repo),
        "description_chars": len(desc),
        "listing_tokens_est": (len(name) + len(desc)) // 4,
        "skill_md_tokens_est": len(text) // 4,
        "skill_md_lines": lines,
        "issues": issues,
    }


def main(argv):
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    mcp, targets, all_ = None, [], False
    it = iter(argv)
    for a in it:
        if a == "--all":
            all_ = True
        elif a == "--repo":
            repo = os.path.abspath(next(it, ""))
        elif a == "--mcp":
            mcp = set(filter(None, next(it, "").split(",")))
        elif a.startswith("-"):
            print(f"error: unknown option {a}", file=sys.stderr)
            return 2
        else:
            targets.append(a)
    if all_ == bool(targets):
        print("error: give skill names or paths, or --all (not both)", file=sys.stderr)
        return 2
    index = skills_in(repo)
    dirs = []
    for t in (sorted(index.values()) if all_ else targets):
        if all_:
            dirs.append(t)
            continue
        cand = [os.path.join(repo, t), t]
        hit = next((c for c in cand if os.path.isfile(os.path.join(c, "SKILL.md"))), None) \
            or index.get(os.path.basename(t.rstrip("/")))
        if not hit:
            print(f"error: no skill named or at '{t}'", file=sys.stderr)
            return 2
        dirs.append(hit)
    results = [check(d, repo, mcp) for d in dirs]
    print(json.dumps({"listing_tokens_total_est": sum(r["listing_tokens_est"] for r in results),
                      "skills": results}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
