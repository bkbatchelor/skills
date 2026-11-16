#!/usr/bin/env bash
# Convert Markdown to PDF, HTML, PNG or JPEG. Wraps convert.mjs and installs its
# npm packages into the skill folder the first time it runs.
#
# Usage: convert.sh [options] <file.md> [more.md ...]     (convert.sh --help lists options)
# Exit codes: 0 ok · 1 conversion failed · 2 usage or missing Node
set -euo pipefail

SKILL="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v node >/dev/null 2>&1 || { echo "convert.sh: node is not installed. Install Node.js 20 or newer and run again." >&2; exit 2; }
node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 20 ? 0 : 1)' \
  || { echo "convert.sh: Node.js 20 or newer is required (found $(node -v))." >&2; exit 2; }

if [ ! -d "$SKILL/node_modules/markdown-it" ]; then
  command -v npm >/dev/null 2>&1 || { echo "convert.sh: npm is not installed." >&2; exit 2; }
  echo "convert.sh: installing packages into $SKILL/node_modules (first run only)..." >&2
  # PUPPETEER_SKIP_DOWNLOAD: puppeteer-core never downloads a browser, but keep it explicit.
  PUPPETEER_SKIP_DOWNLOAD=1 npm ci --omit=dev --no-audit --no-fund --prefix "$SKILL" >&2
fi

exec node "$SKILL/scripts/convert.mjs" "$@"
