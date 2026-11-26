#!/usr/bin/env bash
# Run SkillEvaluator's Tier 2 similarity check over every skill in this repo,
# using OpenRouter for embeddings.
#
# Usage:
#   efficiency/skill-audit/scripts/tier-2-similarity-check.sh [-o <report-dir>] [-r <formats>] [extra args]
#
# Defaults:
#   -o  <repo>/../skills-reports/tier2-collection  (SkillEvaluator rejects a
#       report folder inside the folder it scans)
#   -r  cli,json,html
#
# Environment:
#   OPENROUTER_KEY_VAR   name of the variable that holds the OpenRouter key
#                        (default: ORCA_OPENROUTER_API_KEY, then OPENROUTER_API_KEY)
#   SKILL_EVAL_EMBEDDING_MODEL   embeddings model (default: openai/text-embedding-3-small)
#
# The key is read from the environment and is never printed.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
out="$repo/../skills-reports/tier2-collection"
formats="cli,json,html"
extra=()

while [ $# -gt 0 ]; do
  case $1 in
    -o|--output-dir) out=${2:?missing value for $1}; shift 2 ;;
    -r|--report)     formats=${2:?missing value for $1}; shift 2 ;;
    -h|--help)       sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)               extra+=("$1"); shift ;;
  esac
done

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

out=$(realpath -m "$out")
mkdir -p "$out"
exec skillevaluator similarity-check "$repo" --type skill -r "$formats" -o "$out" ${extra[@]+"${extra[@]}"}
