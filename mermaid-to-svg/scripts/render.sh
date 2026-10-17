#!/usr/bin/env bash
# Render Mermaid diagrams to SVG with mermaid-cli (mmdc), then validate the output.
#
# Usage: render.sh [options] <input> [output] [-- extra mmdc args...]
#
#   <input>   .mmd/.mermaid file, a Markdown file (every ```mermaid block is rendered),
#             or - to read one diagram from stdin
#   [output]  .svg path (default: <input>.svg; stdin requires it). With Markdown input,
#             <dir>/<stem>.svg produces <dir>/<stem>-1.svg, <stem>-2.svg, ... and a .md
#             output writes a copy of the Markdown with each block replaced by an image link.
#
# Options:
#   --portable        Draw labels as SVG <text> instead of HTML <foreignObject>, so the file
#                     renders outside browsers (Inkscape, rsvg, ImageMagick, Office, PDFs)
#   -t, --theme T     default | neutral | dark | forest | base (and the other mmdc themes)
#   -b, --background  Background colour, e.g. transparent, white, '#F0F0F0'
#   -c, --config F    Mermaid JSON config file (merged with --portable when both are given)
#
# Env: MERMAID_CLI_VERSION (default 12.0.0) · PUPPETEER_EXECUTABLE_PATH (auto-detected)
#      MERMAID_NO_SANDBOX=1 forces Chrome's --no-sandbox (automatic when running as root)
#
# Prints each SVG written, one per line, on stdout. Logs go to stderr.
# Exit codes: 0 rendered and valid · 1 mmdc failed · 2 usage · 3 nothing rendered or invalid SVG
set -euo pipefail

usage() { sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
die() { echo "render.sh: $1" >&2; exit "${2:-2}"; }

portable=0 theme="" background="" config=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --portable) portable=1; shift ;;
    -t|--theme) [[ $# -ge 2 ]] || usage; theme=$2; shift 2 ;;
    -b|--background) [[ $# -ge 2 ]] || usage; background=$2; shift 2 ;;
    -c|--config) [[ $# -ge 2 ]] || usage; config=$2; shift 2 ;;
    -h|--help) usage ;;
    --) break ;;
    -?*) die "unknown option '$1' (pass mmdc options after --)" ;;
    *) break ;;
  esac
done
[[ $# -ge 1 && $1 != -- ]] || usage
input=$1; shift
output=""
if [[ $# -gt 0 && $1 != -- ]]; then output=$1; shift; fi
[[ ${1:-} == -- ]] && shift
extra=("$@")

command -v node >/dev/null || die "node is required (mermaid-cli is a Node.js tool)"
if [[ $input != - ]]; then
  [[ -f $input ]] || die "input not found: $input"
fi
if [[ -z $output ]]; then
  [[ $input != - ]] || die "an output path is required when reading from stdin"
  output="${input%.*}.svg"
fi
[[ -z $config || -f $config ]] || die "config file not found: $config"
outdir=$(dirname "$output")
mkdir -p "$outdir"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# --- mmdc command ---------------------------------------------------------------------
if command -v mmdc >/dev/null; then
  mmdc=(mmdc)
else
  mmdc=(npx -y "@mermaid-js/mermaid-cli@${MERMAID_CLI_VERSION:-12.0.0}")
fi

# Reuse a system Chrome/Chromium instead of letting puppeteer download its own.
if [[ -z ${PUPPETEER_EXECUTABLE_PATH:-} ]]; then
  for b in chromium chromium-browser google-chrome-stable google-chrome; do
    if p=$(command -v "$b"); then
      export PUPPETEER_EXECUTABLE_PATH=$p PUPPETEER_SKIP_DOWNLOAD=1
      break
    fi
  done
fi

args=(-i "$input" -o "$output")
[[ -n $theme ]] && args+=(-t "$theme")
[[ -n $background ]] && args+=(-b "$background")

if [[ $portable == 1 ]]; then
  # Mermaid 11+ reads htmlLabels at the top level; flowchart.htmlLabels is ignored.
  node -e '
    const fs = require("fs");
    const [src, dst] = process.argv.slice(1);
    const cfg = src ? JSON.parse(fs.readFileSync(src, "utf8")) : {};
    cfg.htmlLabels = false;
    fs.writeFileSync(dst, JSON.stringify(cfg));
  ' "$config" "$tmp/config.json"
  args+=(-c "$tmp/config.json")
elif [[ -n $config ]]; then
  args+=(-c "$config")
fi

has_puppeteer_cfg=0
for a in "${extra[@]}"; do [[ $a == -p || $a == --puppeteerConfigFile ]] && has_puppeteer_cfg=1; done
if [[ $has_puppeteer_cfg == 0 && ( ${MERMAID_NO_SANDBOX:-} == 1 || $EUID -eq 0 ) ]]; then
  echo '{"args":["--no-sandbox"]}' > "$tmp/puppeteer.json"
  args+=(-p "$tmp/puppeteer.json")
fi

# --- render ---------------------------------------------------------------------------
# Markdown input writes numbered files, so remember which SVGs already existed.
touch "$tmp/start"
case $input in *.md|*.markdown) sleep 1 ;; esac   # -newer compares whole seconds on some filesystems
"${mmdc[@]}" "${args[@]}" "${extra[@]}" >&2 || die "mmdc failed (see the error above)" 1

# --- collect and validate -------------------------------------------------------------
svgs=()
case $input in
  *.md|*.markdown)
    artefacts=$outdir
    for ((i = 0; i < ${#extra[@]}; i++)); do
      [[ ${extra[i]} == -a || ${extra[i]} == --artefacts ]] && artefacts=${extra[i+1]:-$outdir}
    done
    stem=$(basename "${output%.*}")
    while IFS= read -r f; do svgs+=("$f"); done < <(
      find "$artefacts" -maxdepth 1 -name "${stem}-*.svg" -newer "$tmp/start" | sort -V)
    [[ ${#svgs[@]} -gt 0 ]] || die "no mermaid blocks were rendered from $input" 3
    ;;
  *)
    [[ $output == *.svg ]] || { echo "$output"; exit 0; }   # png/pdf requested via output name
    svgs=("$output")
    ;;
esac

bad=0
for f in "${svgs[@]}"; do
  if [[ ! -s $f ]] || ! grep -q '<svg' "$f"; then
    echo "render.sh: $f is empty or not an SVG" >&2; bad=1; continue
  fi
  if command -v xmllint >/dev/null && ! xmllint --noout "$f" 2>/dev/null; then
    echo "render.sh: $f is not well-formed XML" >&2; bad=1; continue
  fi
  if grep -q 'Syntax error in text' "$f"; then
    echo "render.sh: $f contains Mermaid's syntax-error diagram" >&2; bad=1; continue
  fi
  # Mermaid splits <text> labels into one <tspan> per word with the space leading the next
  # word. Non-browser renderers (rsvg, ImageMagick) collapse that space, so "two words"
  # shows as "twowords". Preserve whitespace, which is safe because mmdc's SVG is unindented.
  if [[ $portable == 1 ]] && ! grep -q 'xml:space="preserve"' "$f"; then
    sed -i 's/<text /<text xml:space="preserve" /g' "$f"
  fi
  echo "$f"
done
[[ $bad == 0 ]] || exit 3
