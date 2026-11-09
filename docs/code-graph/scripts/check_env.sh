#!/usr/bin/env bash
# Report whether codegraph is installed and whether a repo is indexed.
#   check_env.sh [repo]      repo defaults to the current directory
# Exit 0: installed and indexed. 1: codegraph missing. 2: installed, repo not indexed.
set -u
repo="${1:-.}"
if ! command -v codegraph >/dev/null 2>&1; then
  echo "codegraph: missing"
  exit 1
fi
echo "codegraph: installed ($(codegraph --version 2>&1 | head -1))"
top=$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null || (cd "$repo" && pwd -P))
if [ -d "$top/.codegraph" ]; then
  echo "index: present ($top/.codegraph)"
  exit 0
fi
echo "index: absent ($top)"
exit 2
