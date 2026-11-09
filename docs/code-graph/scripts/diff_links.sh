#!/usr/bin/env bash
# List documents that may constrain the files changed in the working tree, and say whether the docs graph is stale.
#   diff_links.sh [--base REF] [repo]     REF defaults to HEAD (staged, unstaged and untracked files count)
# Output lines:  applies_to <doc> <file>   the doc lists the file in its front matter
#                mention    <doc> <file>   the doc's text names the file
#                docs-graph: missing | ok | stale   (graph.json older than the newest Markdown file)
# Read-only. Symbols are not matched here; the caller maps symbols with codegraph and queries the docs graph.
set -u
base=HEAD
[ "${1:-}" = "--base" ] && { base="$2"; shift 2; }
repo="$(git -C "${1:-.}" rev-parse --show-toplevel)" || exit 2
cd "$repo" || exit 2

changed=$( { git diff --name-only "$base" --; git ls-files --others --exclude-standard; } | sort -u)
docs=$(git ls-files '*.md' | grep -vE '(^|/)(node_modules|CHANGELOG)' || true)
[ -n "$changed" ] && [ -n "$docs" ] && while IFS= read -r f; do
  [ -z "$f" ] && continue
  while IFS= read -r d; do
    [ "$d" = "$f" ] && continue
    if awk -v f="$f" 'NR==1&&$0!="---"{exit} NR>1&&$0=="---"{exit} index($0,f){found=1} END{exit !found}' "$d"; then
      echo "applies_to $d $f"
    elif grep -qF -- "$f" "$d"; then
      echo "mention $d $f"
    fi
  done <<< "$docs"
done <<< "$changed"

graph=""
for g in "graphify-out/graph.json" "$HOME/curated/$(basename "$repo")/graphify-out/graph.json"; do
  [ -f "$g" ] && { graph="$g"; break; }
done
if [ -z "$graph" ]; then echo "docs-graph: missing"; exit 0; fi
newest=$( [ -n "$docs" ] && printf '%s\n' "$docs" | xargs -d '\n' stat -c %Y 2>/dev/null | sort -n | tail -1 )
if [ -n "${newest:-}" ] && [ "$(stat -L -c %Y "$graph")" -lt "$newest" ]; then
  echo "docs-graph: stale $graph"
else
  echo "docs-graph: ok $graph"
fi
