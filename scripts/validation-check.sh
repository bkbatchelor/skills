#!/usr/bin/env bash
# Run SkillEvaluator's Tier 1 static validation without any LLM (no API key, no
# model spend) on one or more skills.
#
# Usage:
#   scripts/validation-check.sh [options] <skill>... [-- <tier1 args>]
#   scripts/validation-check.sh [options] --all [-- <tier1 args>]
#
#   <skill>        a skill name (generate-readme) or a path (docs/generate-readme)
#   --all          check every folder in the repo that holds a SKILL.md
#   -o <dir>       root folder for reports, one subfolder per skill
#                  (default: <repo>/../skills-reports/validation)
#   -h, --help     show this help
#
# Everything after `--` goes to `skillevaluator tier1` unchanged, for example:
#   -- --min-score 80 --skip secrets
# The script always adds --no-llm and always writes a JSON report (it reads it
# for the summary), whatever -r you pass.
#
# Exit codes: 0 every skill passed; 1 a skill failed or was INCOMPLETE (for
# example a scanner could not finish); 2 usage error, missing CLI or a required
# scanner missing.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
out="$repo/../skills-reports/validation"
all=0
skills=() passthru=()

usage_err() { echo "error: $*" >&2; echo "try: scripts/validation-check.sh --help" >&2; exit 2; }

while [ $# -gt 0 ]; do
  case $1 in
    --all)     all=1; shift ;;
    -o)        out=${2:?missing value for -o}; shift 2 ;;
    -h|--help) sed -n '2,21p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --)        shift; passthru=("$@"); break ;;
    -*)        usage_err "unknown option: $1" ;;
    *)         skills+=("$1"); shift ;;
  esac
done

command -v skillevaluator >/dev/null || { echo "error: skillevaluator is not installed" >&2; exit 2; }

if [ "$all" = 1 ]; then
  [ ${#skills[@]} -eq 0 ] || usage_err "--all cannot be combined with skill names"
  mapfile -t paths < <(cd "$repo" && find . -name SKILL.md -not -path './.git/*' -not -path '*/node_modules/*' \
    | sed 's|^\./||; s|/SKILL.md$||' | sort)
else
  [ ${#skills[@]} -gt 0 ] || usage_err "give at least one skill, or --all"
  paths=()
  for s in "${skills[@]}"; do
    if [ -f "$repo/$s/SKILL.md" ]; then
      paths+=("$s")
    else
      mapfile -t hit < <(cd "$repo" && find . -type d -name "$s" -not -path './.git/*' -not -path '*/node_modules/*' \
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

# Scanner readiness: stop before any skill if a required scanner fails.
# Semgrep is optional and only warned about. (This may download pinned
# scanners the first time, as health-check does.)
health=$(skillevaluator health-check --tier 1 2>&1 || true)
if ! echo "$health" | grep -qE '^ *CLI package +pass' \
   || echo "$health" | grep -qE '^ *(SkillSpector|Bandit|Gitleaks) +fail'; then
  echo "$health" >&2
  echo "error: a required Tier 1 scanner is missing or failing; fix the rows above" >&2
  exit 2
fi
echo "$health" | grep -E '^ *Semgrep .* fail' >/dev/null && echo "warning: Semgrep is not installed (optional)" >&2

out=$(realpath -m "$out")
mkdir -p "$out"

for p in "${paths[@]}"; do
  name=$(basename "$p")
  echo
  echo "=== $p"
  # Exit 1 means a gate failed; the summary below reports it, so keep going.
  skillevaluator tier1 "$repo/$p" --no-llm -o "$out/$name" ${passthru[@]+"${passthru[@]}"} -r json,cli || true
done

python3 -I - "$out" "${paths[@]}" <<'PY'
import json, os, sys
out, paths = sys.argv[1], sys.argv[2:]
rows, failed = [], False
for p in paths:
    name = os.path.basename(p)
    f = os.path.join(out, name, "skillevaluator-tier1.json")
    try:
        d = json.load(open(f))
        q = (d.get("quality_summary") or [{}])[0]
        score = q.get("overall_score")
        score = "-" if score is None else f"{score:.0f} {q.get('grade', '')}".strip()
        sev = d.get("severity_counts", {})
        hc = sev.get("critical", 0) + sev.get("high", 0)
        gate = {"passed": "PASS", "failed": "FAIL", "incomplete": "INCOMPLETE"}.get(
            d.get("overall_status"), str(d.get("overall_status")).upper())
    except Exception:
        score, hc, gate = "-", "-", "NO REPORT"
    failed |= gate != "PASS"
    rows.append((name, score, gate, str(hc)))
hdr = ("skill", "quality", "gate", "high+crit")
w = [max(len(r[i]) for r in rows + [hdr]) for i in range(4)]
print("\nSummary (Tier 1, no LLM)")
for r in [hdr] + rows:
    print("  ".join(c.ljust(w[i]) for i, c in enumerate(r)))
print(f"\nReports: {out}/<skill>/")
sys.exit(1 if failed else 0)
PY
