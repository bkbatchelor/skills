#!/usr/bin/env bash
# Screenshot an HTML artifact at desktop and mobile widths and report console errors.
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
for size in 1280x2600 390x3200; do
  png="$out/$stem-${size%%x*}.png"
  log=$("$chrome" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
    --enable-logging=stderr --v=0 --virtual-time-budget=3000 \
    --window-size="${size/x/,}" --screenshot="$png" "file://$file" 2>&1 || true)
  if grep -E 'CONSOLE.*(Uncaught|error|Error)' <<<"$log" >&2; then status=1; fi
  [[ -s $png ]] || { echo "FAIL: no screenshot at $size" >&2; status=1; continue; }
  echo "shot: $png"
done

# Offline rule: no external URLs may be loaded by the file.
if grep -nE '(src|href)=["'"'"']https?://|@import|url\(["'"'"']?https?://' "$file" >&2; then
  echo "FAIL: external dependency found" >&2; status=1
fi
[[ $status -eq 0 ]] && echo "OK: rendered, no console errors, no external deps"
exit $status
