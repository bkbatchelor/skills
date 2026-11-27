#!/usr/bin/env bash
# Run SkillEvaluator's Tier 1 harness-check (advisory, keyless) for the Claude,
# Gemini and Copilot harnesses on one or more skills.
#
# Usage:
#   efficiency/skill-audit/scripts/tier-1-harness-check.sh [options] <skill>... [-- <harness-check args>]
#   efficiency/skill-audit/scripts/tier-1-harness-check.sh [options] --all [-- <harness-check args>]
#
#   <skill>        a skill name (generate-readme) or a path (docs/generate-readme)
#   --all          check every folder in the repo that holds a SKILL.md
#   --strict       exit 1 if any harness drops or degrades a skill
#   -o <dir>       folder for the per-skill JSON files
#                  (default: <repo>/../skills-reports/harness-check)
#   -h, --help     show this help
#
# Everything after `--` goes to `skillevaluator harness-check` unchanged, for
# example: -- --headless --context-tokens 200000
#
# Harnesses: claude-code and copilot-cli are checked. SkillEvaluator ships no
# Gemini profile, so Gemini is reported as "n/a". To add one later, put a
# profile YAML in a folder and pass `-- --harness-profiles <folder>`, then add
# its name to HARNESSES below.
#
# Exit codes: 0 ran (advisory), 1 --strict and a skill is dropped or degraded,
# 2 usage error or skillevaluator missing.
set -euo pipefail

# Audit the repo you run from, so a symlinked install (.claude/skills/...) works.
# Fall back to this script's own location when not inside a git repo.
repo=$(git rev-parse --show-toplevel 2>/dev/null || { cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../../.." && pwd; })
out="$repo/../skills-reports/harness-check"
HARNESSES="claude-code,copilot-cli"
all=0 strict=0
skills=() passthru=()

usage_err() { echo "error: $*" >&2; echo "try: efficiency/skill-audit/scripts/tier-1-harness-check.sh --help" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case $1 in
    --all)     all=1; shift ;;
    --strict)  strict=1; shift ;;
    -o)        out=${2:?missing value for -o}; shift 2 ;;
    -h|--help) sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --)        shift; passthru=("$@"); break ;;
    -*)        usage_err "unknown option: $1" ;;
    *)         skills+=("$1"); shift ;;
  esac
done

command -v skillevaluator >/dev/null || { echo "error: skillevaluator is not installed" >&2; exit 2; }

if [ "$all" = 1 ]; then
  [ ${#skills[@]} -eq 0 ] || usage_err "--all cannot be combined with skill names"
  mapfile -t paths < <(cd "$repo" && find . -name SKILL.md -not -path './.*/*' -not -path '*/node_modules/*' \
    | sed 's|^\./||; s|/SKILL.md$||' | sort)
else
  [ ${#skills[@]} -gt 0 ] || usage_err "give at least one skill, or --all"
  paths=()
  for s in "${skills[@]}"; do
    if [ -f "$repo/$s/SKILL.md" ]; then
      paths+=("$s")
    else
      mapfile -t hit < <(cd "$repo" && find . -type d -name "$s" -not -path './.*/*' -not -path '*/node_modules/*' \
        -exec test -f '{}/SKILL.md' ';' -print | sed 's|^\./||')
      case ${#hit[@]} in
        0) usage_err "no skill named or at '$s'" ;;
        1) paths+=("${hit[0]}") ;;
        *) usage_err "'$s' is ambiguous: ${hit[*]}" ;;
      esac
    fi
  done
fi
[ ${#paths[@]} -gt 0 ] || usage_err "no skills found"

out=$(realpath -m "$out")
mkdir -p "$out"

for p in "${paths[@]}"; do
  echo
  skillevaluator harness-check "$repo/$p" --harness "$HARNESSES" \
    --json "$out/$(basename "$p").json" ${passthru[@]+"${passthru[@]}"}
done

python3 -I - "$out" "$strict" "${paths[@]}" <<'PY'
import json, os, sys
out, strict, paths = sys.argv[1], sys.argv[2] == "1", sys.argv[3:]
cols = ["claude-code", "gemini", "copilot-cli"]
rows, bad = [], False
for p in paths:
    name = os.path.basename(p)
    with open(os.path.join(out, name + ".json")) as f:
        block = json.load(f)["harness_compatibility"]
    status = {r["harness"]: r["status"] for runs in block.values() for r in runs}
    status["gemini"] = "n/a"
    bad |= any(status.get(c) not in ("loads", "n/a") for c in cols)
    rows.append((name, [status.get(c, "?") for c in cols]))
w = max(len(r[0]) for r in rows + [("skill", [])])
print("\nSummary")
print(f"{'skill':<{w}}  " + "  ".join(f"{c:<12}" for c in cols))
for n, st in rows:
    print(f"{n:<{w}}  " + "  ".join(f"{s:<12}" for s in st))
print(f"\nJSON: {out}")
print("Gemini: no SkillEvaluator profile, not checked.")
sys.exit(1 if strict and bad else 0)
PY
