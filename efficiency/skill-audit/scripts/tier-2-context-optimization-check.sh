#!/usr/bin/env bash
# Run SkillEvaluator's Tier 2 context-optimization-check (redundant content
# inside one skill) on one or more skills, using OpenRouter for embeddings and
# the LLM review of each cluster.
#
# Usage:
#   efficiency/skill-audit/scripts/tier-2-context-optimization-check.sh [options] <skill>... [-- <check args>]
#   efficiency/skill-audit/scripts/tier-2-context-optimization-check.sh [options] --all [-- <check args>]
#
#   <skill>        a skill name (generate-readme) or a path (docs/generate-readme)
#   --all          check every folder in the repo that holds a SKILL.md
#   -o <dir>       root folder for reports, one subfolder per skill, plus a
#                  run-<timestamp>.log (default:
#                  <repo>/../skills-reports/context-optimization)
#   -h, --help     show this help
#
# Everything after `--` goes to `skillevaluator context-optimization-check`
# unchanged, for example: -- --threshold 0.85
#
# Harnesses: the check reads only the skill's own files, so one result applies
# to Claude Code, Codex and GitHub Copilot alike. Loading per harness is checked
# by tier-1-harness-check.sh.
#
# When a skill fails the check, is not found, or the check errors, the script
# logs the reason and goes on to the next skill.
#
# Environment:
#   OPENROUTER_KEY_VAR           name of the variable that holds the OpenRouter key
#                                (default: ORCA_OPENROUTER_API_KEY, then OPENROUTER_API_KEY)
#   SKILL_EVAL_EMBEDDING_MODEL   embeddings model (default: openai/text-embedding-3-small)
#   SKILL_EVAL_LLM_MODEL         LLM model (default: anthropic/claude-haiku-4.5)
# The key is read from the environment and is never printed.
#
# Exit codes: 0 every skill passed; 1 a skill failed, was INCOMPLETE or was not
# found; 2 usage error, skillevaluator missing or no OpenRouter key.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
me="efficiency/skill-audit/scripts/$(basename "${BASH_SOURCE[0]}")"
out="$repo/../skills-reports/context-optimization"
all=0
skills=() passthru=()

usage_err() { echo "error: $*" >&2; echo "try: $me --help" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case $1 in
    --all)     all=1; shift ;;
    -o)        out=${2:?missing value for -o}; shift 2 ;;
    -h|--help) sed -n '2,37p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --)        shift; passthru=("$@"); break ;;
    -*)        usage_err "unknown option: $1" ;;
    *)         skills+=("$1"); shift ;;
  esac
done

if [ "$all" = 1 ]; then
  [ ${#skills[@]} -eq 0 ] || usage_err "--all cannot be combined with skill names"
else
  [ ${#skills[@]} -gt 0 ] || usage_err "give at least one skill, or --all"
fi

command -v skillevaluator >/dev/null || { echo "error: skillevaluator is not installed" >&2; exit 2; }

key_var=${OPENROUTER_KEY_VAR:-}
if [ -z "$key_var" ]; then
  for v in ORCA_OPENROUTER_API_KEY OPENROUTER_API_KEY; do
    if [ -n "${!v:-}" ]; then key_var=$v; break; fi
  done
fi
if [ -z "$key_var" ] || [ -z "${!key_var:-}" ]; then
  echo "error: no OpenRouter key found. Export ORCA_OPENROUTER_API_KEY or OPENROUTER_API_KEY," >&2
  echo "       or set OPENROUTER_KEY_VAR to the name of your key variable." >&2
  exit 2
fi

export SKILL_EVAL_LLM_PROVIDER=openai-compatible
export SKILL_EVAL_LLM_BASE_URL=https://openrouter.ai/api/v1
export SKILL_EVAL_LLM_API_KEY=${!key_var}
export SKILL_EVAL_EMBEDDING_MODEL=${SKILL_EVAL_EMBEDDING_MODEL:-openai/text-embedding-3-small}
export SKILL_EVAL_LLM_MODEL=${SKILL_EVAL_LLM_MODEL:-anthropic/claude-haiku-4.5}

out=$(realpath -m "$out")
mkdir -p "$out"
log="$out/run-$(date +%Y%m%d-%H%M%S).log"
: > "$log"

# Summary rows: name<TAB>status<TAB>reason
summary="$out/.summary.$$"
: > "$summary"
trap 'rm -f "$summary"' EXIT

record() {  # name status reason
  local reason=${3//$'\t'/ }
  reason=${reason//$'\n'/ }
  printf '%s\t%s\t%s\n' "$1" "$2" "$reason" >> "$summary"
  printf '%s  %-10s %s  %s\n' "$(date +%H:%M:%S)" "$2" "$1" "$reason" >> "$log"
}

# Build the list of skill paths. A name that does not match is logged and skipped.
paths=()
if [ "$all" = 1 ]; then
  mapfile -t paths < <(cd "$repo" && find . -name SKILL.md -not -path './.git/*' -not -path '*/node_modules/*' \
    | sed 's|^\./||; s|/SKILL.md$||' | sort)
else
  for s in "${skills[@]}"; do
    s=${s%/}
    if [ -f "$repo/$s/SKILL.md" ]; then
      paths+=("$s")
    else
      mapfile -t hit < <(cd "$repo" && find . -type d -name "$(basename "$s")" -not -path './.git/*' \
        -not -path '*/node_modules/*' -exec test -f '{}/SKILL.md' ';' -print | sed 's|^\./||')
      case ${#hit[@]} in
        0) echo "skip: no skill named or at '$s'" >&2; record "$s" NOT-FOUND "no skill named or at '$s'" ;;
        1) paths+=("${hit[0]}") ;;
        *) echo "skip: '$s' is ambiguous: ${hit[*]}" >&2; record "$s" NOT-FOUND "ambiguous: ${hit[*]}" ;;
      esac
    fi
  done
fi
[ ${#paths[@]} -gt 0 ] || [ -s "$summary" ] || usage_err "no skills found"

# Reason for a failed skill: its top findings, else the report's errors, else
# the exit code and the end of stderr.
reason_for() {  # json errfile rc
  python3 -I - "$1" "$2" "$3" <<'PY'
import json, sys
jf, ef, rc = sys.argv[1:]
try:
    d = json.load(open(jf))
    status = d.get("overall_status", "failed")
    finds = [f for r in d.get("results", []) for f in r.get("findings", [])]
    if finds:
        parts = [f"{f.get('severity', '?')} {f.get('file_path', '?')}:{f.get('line_number', '?')} "
                 f"{f.get('message', '').splitlines()[0].rstrip(':')}" for f in finds[:3]]
        more = f" (+{len(finds) - 3} more)" if len(finds) > 3 else ""
        print(f"{status.upper()}|{len(finds)} finding(s): " + "; ".join(parts) + more)
        sys.exit()
    errs = [e for r in d.get("results", []) for e in (r.get("legacy") or {}).get("errors", [])]
    if errs:
        print(f"{status.upper()}|" + " ".join(errs[0].split())[:300])
        sys.exit()
    print(f"{status.upper()}|exit {rc}, report has no findings or errors")
except Exception:
    try:
        lines = [l.strip() for l in open(ef, errors="replace") if l.strip()]
    except OSError:
        lines = []
    tail = " / ".join(lines[-3:]) or "no output"
    print(f"ERROR|exit {rc}: {tail[:300]}")
PY
}

for p in "${paths[@]}"; do
  name=$(basename "$p")
  dir="$out/$name"
  rm -rf "$dir"; mkdir -p "$dir"
  echo
  echo "=== $p"
  rc=0
  skillevaluator context-optimization-check "$repo/$p" -r cli,json,html -o "$dir" \
    ${passthru[@]+"${passthru[@]}"} 2> >(tee "$dir/stderr.log" >&2) || rc=$?
  wait  # let the stderr tee finish before reading the file
  if [ "$rc" = 0 ]; then
    record "$name" PASS "no redundant content above the threshold"
  else
    r=$(reason_for "$dir/skillevaluator-context.json" "$dir/stderr.log" "$rc")
    echo "fail: $name: ${r#*|}" >&2
    record "$name" "${r%%|*}" "${r#*|}"
  fi
done

python3 -I - "$summary" "$out" "$log" <<'PY'
import sys
summary, out, log = sys.argv[1:]
rows = [l.rstrip("\n").split("\t", 2) for l in open(summary) if l.strip()]
hdr = ["skill", "status", "reason"]
w = [max(len(r[i]) for r in rows + [hdr]) for i in range(2)]
print("\nSummary (Tier 2 context optimization; applies to claude-code, codex, copilot-cli)")
for r in [hdr] + rows:
    reason = r[2] if len(r[2]) <= 140 else r[2][:137] + "..."
    print(f"{r[0]:<{w[0]}}  {r[1]:<{w[1]}}  {reason}")
passed = sum(r[1] == "PASS" for r in rows)
print(f"\n{passed} of {len(rows)} passed")
print(f"Reports: {out}/<skill>/")
print(f"Log:     {log}")
sys.exit(0 if passed == len(rows) else 1)
PY
