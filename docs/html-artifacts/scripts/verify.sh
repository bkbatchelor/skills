#!/usr/bin/env bash
# Screenshot an HTML artifact at desktop and mobile widths, in default and forced-dark themes,
# and report console errors.
# Usage: verify.sh <file.html> [out-dir]   (out-dir defaults to the file's directory)
set -euo pipefail

file=${1:?usage: verify.sh <file.html> [out-dir]}
[[ -f $file ]] || { echo "FAIL: $file not found" >&2; exit 2; }
file=$(realpath "$file")
out=${2:-$(dirname "$file")/.shots}
mkdir -p "$out"

chrome=$(command -v chromium || command -v chromium-browser || command -v google-chrome || command -v google-chrome-stable || true)
[[ -n $chrome ]] || { echo "FAIL: no Chromium/Chrome found; cannot verify render" >&2; exit 3; }

stem=$(basename "${file%.html}")
status=0
# Light/OS default plus a forced-dark copy (headless Chromium ignores the OS scheme).
dark_copy="$out/$stem.dark.html"
sed 's/<html\([^>]*\)>/<html\1 data-theme="dark">/' "$file" > "$dark_copy"
trap 'rm -f "$dark_copy"' EXIT

shoot() { # <html file> <width x height> <png> <label>
  local log
  log=$("$chrome" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
    --enable-logging=stderr --v=0 --virtual-time-budget=3000 \
    --window-size="${2/x/,}" --screenshot="$3" "file://$1" 2>&1 || true)
  if grep -E 'CONSOLE.*(Uncaught|error|Error)' <<<"$log" >&2; then status=1; fi
  [[ -s $3 ]] || { echo "FAIL: no screenshot ($4)" >&2; status=1; return; }
  echo "shot: $3"
}

for size in 1280x2600 390x3200; do
  shoot "$file" "$size" "$out/$stem-${size%%x*}.png" "default ${size%%x*}"
  shoot "$dark_copy" "$size" "$out/$stem-${size%%x*}-dark.png" "dark ${size%%x*}"
done

# Offline rule: no external URLs may be loaded by the file.
if grep -nE '(src|href)=["'"'"']https?://|@import|url\(["'"'"']?https?://' "$file" >&2; then
  echo "FAIL: external dependency found" >&2; status=1
fi
[[ $status -eq 0 ]] && echo "OK: rendered, no console errors, no external deps"
exit $status
