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
#   --style modern    Apply the Archify-inspired modern look (rounded tinted nodes, dashed
#                     groups, monospace font, diagram enclosed in a rounded frame). Forces the
#                     base theme; -c settings override it
#   --style-mode M    dark (default) | light, for --style modern
#   --canvas C        Background for --style modern (implies it): blank (default) | dots |
#                     grid | blueprint | editorial, each in the dark or light mode.
#                     Sets the background colour unless -b is given
#   --png             Also write a PNG beside each SVG (same stem; Markdown gives <stem>-N.png).
#                     PNG background is transparent unless -b is given
#   --scale N         PNG pixel scale factor (default 2); implies --png
#   --size N          Cap the PNG's longest side at N pixels (mmdc --size); implies --png
#
# Env: MERMAID_CLI_VERSION (default 12.0.0) · PUPPETEER_EXECUTABLE_PATH (auto-detected)
#      MERMAID_NO_SANDBOX=1 forces Chrome's --no-sandbox (automatic when running as root)
#
# Prints each SVG written, then each PNG, one per line, on stdout. Logs go to stderr.
# Exit codes: 0 rendered and valid · 1 mmdc failed · 2 usage · 3 nothing rendered or invalid SVG
set -euo pipefail

usage() { sed -n '2,34p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
die() { echo "render.sh: $1" >&2; exit "${2:-2}"; }
# Prints the root viewBox size of an SVG as "W H", rounded up to whole pixels.
svg_size() {
  local w h
  read -r w h <<< "$(grep -o -m1 '<svg [^>]*>' "$1" | sed -n 's/.*viewBox="[^ ]* [^ ]* \([0-9.]*\) \([0-9.]*\)".*/\1 \2/p')"
  [[ -n ${w:-} && -n ${h:-} ]] || die "cannot read the viewBox of $1" 3
  awk -v w="$w" -v h="$h" 'BEGIN { print int(w + 0.999), int(h + 0.999) }'
}

portable=0 theme="" background="" config="" png=0 scale="" size="" style="" style_mode=dark canvas=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --portable) portable=1; shift ;;
    -t|--theme) [[ $# -ge 2 ]] || usage; theme=$2; shift 2 ;;
    -b|--background) [[ $# -ge 2 ]] || usage; background=$2; shift 2 ;;
    -c|--config) [[ $# -ge 2 ]] || usage; config=$2; shift 2 ;;
    --style) [[ $# -ge 2 ]] || usage; style=$2; shift 2 ;;
    --canvas) [[ $# -ge 2 ]] || usage; canvas=$2; shift 2 ;;
    --style-mode) [[ $# -ge 2 ]] || usage; style_mode=$2; shift 2 ;;
    --png) png=1; shift ;;
    --scale) [[ $# -ge 2 ]] || usage; scale=$2; png=1; shift 2 ;;
    --size) [[ $# -ge 2 ]] || usage; size=$2; png=1; shift 2 ;;
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
[[ -z $scale || $scale =~ ^[0-9]+(\.[0-9]+)?$ ]] || die "--scale must be a number: $scale"
[[ -z $size || $size =~ ^[0-9]+$ ]] || die "--size must be an integer: $size"
[[ $png == 0 || $output == *.svg || $input == *.md || $input == *.markdown ]] || die "--png needs an .svg output path"
[[ -z $config || -f $config ]] || die "config file not found: $config"
[[ -z $style || $style == modern ]] || die "--style must be 'modern': $style"
[[ $style_mode == dark || $style_mode == light ]] || die "--style-mode must be dark or light: $style_mode"
[[ -z $canvas ]] || style=${style:-modern}
style_file="" canvas_css="" canvas_bg="" frame_stroke=""
if [[ -n $style ]]; then
  styles_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/styles"
  style_file="$styles_dir/$style-$style_mode.json"
  [[ -f $style_file ]] || die "style file not found: $style_file"
  theme=base
  canvas=${canvas:-blank}
  # Prints the canvas page colour, then its root-element CSS (empty for blank).
  canvas_info=$(node -e '
    const [file, name, mode] = process.argv.slice(1);
    const all = JSON.parse(require("fs").readFileSync(file, "utf8"));
    if (!all[name]) { console.error("--canvas must be one of: " + Object.keys(all).join(" | ")); process.exit(2); }
    console.log(all[name][mode].background + "\n" + all[name][mode].css);
  ' "$styles_dir/canvases.json" "$canvas" "$style_mode") || exit 2
  canvas_bg=$(sed -n 1p <<< "$canvas_info")
  canvas_css=$(sed -n 2p <<< "$canvas_info")
  [[ -n $background ]] || background=$canvas_bg
  frame_stroke=$(node -p 'JSON.parse(require("fs").readFileSync(process.argv[1], "utf8")).themeVariables.clusterBorder' "$style_file")
fi
outdir=$(dirname "$output")
mkdir -p "$outdir"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# stdin can only be read once, but --png renders twice.
if [[ $input == - ]]; then
  cat > "$tmp/stdin.mmd"
  input=$tmp/stdin.mmd
fi

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

# mmdc's own PDF export can't paint the canvas pattern, so render an SVG and print it with Chrome.
pdf_final=""
if [[ -n $style_file && $output == *.pdf && $input != *.md && $input != *.markdown ]]; then
  if [[ -n ${PUPPETEER_EXECUTABLE_PATH:-} ]]; then
    pdf_final=$output output=$tmp/pdf-source.svg
  else
    echo "render.sh: no system Chrome found; the PDF will not have the canvas pattern or rounded frame" >&2
  fi
fi
args=(-i "$input" -o "$output")
[[ -n $theme ]] && args+=(-t "$theme")
[[ -n $background ]] && args+=(-b "$background")

if [[ $portable == 1 || -n $style_file ]]; then
  # The style is the base config and the user's -c file overrides it (shallow merge, with
  # themeVariables merged key by key). Mermaid 11+ reads htmlLabels at the top level;
  # flowchart.htmlLabels is ignored.
  node -e '
    const fs = require("fs");
    const [styleFile, src, dst, portable, canvasBg] = process.argv.slice(1);
    const read = (f) => (f ? JSON.parse(fs.readFileSync(f, "utf8")) : {});
    const base = read(styleFile), user = read(src);
    if (canvasBg) {   // keep edge-label pills and pie borders on the canvas colour
      base.themeVariables = { ...base.themeVariables, background: canvasBg, edgeLabelBackground: canvasBg, pieStrokeColor: canvasBg };
      base.themeCSS += `.edgeLabel,.edgeLabel p,.edgeLabel span{background-color:${canvasBg};}.edgeLabel rect{fill:${canvasBg};}`;
    }
    const cfg = { ...base, ...user };
    if (base.themeVariables || user.themeVariables)
      cfg.themeVariables = { ...base.themeVariables, ...user.themeVariables };
    if (base.themeCSS && user.themeCSS) cfg.themeCSS = base.themeCSS + user.themeCSS;
    if (portable === "1") cfg.htmlLabels = false;
    fs.writeFileSync(dst, JSON.stringify(cfg));
  ' "$style_file" "$config" "$tmp/config.json" "$portable" "$canvas_bg"
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
  # Modern style encloses the diagram in a rounded frame and clips the background to it. CSS
  # on a standalone SVG root can't be rounded, so the root background is dropped and redrawn
  # inside the viewBox: a rounded rect for the page colour (works everywhere), a rounded
  # foreignObject div for the canvas pattern (browsers only), then the stroked frame.
  if [[ -n $style_file ]] && ! grep -q 'data-frame' "$f"; then
    node -e '
      const fs = require("fs");
      const [file, stroke, bg, css] = process.argv.slice(1);
      let svg = fs.readFileSync(file, "utf8");
      const m = svg.match(/viewBox="([-\d.]+) ([-\d.]+) ([\d.]+) ([\d.]+)"/);
      if (!m) process.exit(0);
      const pad = 24, r = 20, [x, y, w, h] = m.slice(1).map(Number);
      const [nx, ny, nw, nh] = [x - pad, y - pad, w + 2 * pad, h + 2 * pad];
      const pattern = (css.match(/background-image:[^}]*(?=})/) || [""])[0];
      const rect = (extra) => `<rect x="${nx + 1}" y="${ny + 1}" width="${nw - 2}" height="${nh - 2}" rx="${r}" ry="${r}" ${extra}/>`;
      const layers = rect(`fill="${bg}"`)
        + (pattern ? `<foreignObject x="${nx + 1}" y="${ny + 1}" width="${nw - 2}" height="${nh - 2}"><div xmlns="http://www.w3.org/1999/xhtml" style="width:100%;height:100%;border-radius:${r}px;${pattern}"></div></foreignObject>` : "")
        + rect(`data-frame="1" fill="none" stroke="${stroke}" stroke-width="2"`);
      svg = svg.replace(m[0], `viewBox="${nx} ${ny} ${nw} ${nh}"`)
               .replace(/max-width: [\d.]+px/, `max-width: ${nw}px`)
               .replace(/background-color: [^;"]*;?/, "")
               .replace(/(<svg [^>]*>(?:<style>.*?<\/style>)?)/s, `$1${layers}`);
      fs.writeFileSync(file, svg);
    ' "$f" "$frame_stroke" "${background:-transparent}" "$canvas_css"
  fi
  if [[ $portable == 1 ]] && ! grep -q 'xml:space="preserve"' "$f"; then
    sed -i 's/<text /<text xml:space="preserve" /g' "$f"
  fi
  [[ -n $pdf_final ]] || echo "$f"
done
[[ $bad == 0 ]] || exit 3

if [[ -n $pdf_final ]]; then
  read -r w h <<< "$(svg_size "$output")"
  printf '<!doctype html><meta charset="utf-8"><style>@page{size:%spx %spx;margin:0}html,body{margin:0}svg{display:block;width:%spx;height:%spx;max-width:none!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}</style>' "$w" "$h" "$w" "$h" > "$tmp/pdf.html"
  cat "$output" >> "$tmp/pdf.html"
  "$PUPPETEER_EXECUTABLE_PATH" --headless --no-sandbox --disable-gpu --no-pdf-header-footer \
    --print-to-pdf="$pdf_final" "file://$tmp/pdf.html" >&2 || die "Chrome failed while rendering the PDF" 1
  [[ $(head -c4 "$pdf_final") == %PDF ]] || die "$pdf_final is not a PDF" 3
  echo "$pdf_final"
  exit 0
fi

# --- PNG ------------------------------------------------------------------------------
[[ $png == 1 ]] || exit 0
pngout="${output%.*}.png"
pargs=(-i "$input" -o "$pngout" -b "${background:-transparent}" -s "${scale:-2}")
[[ -n $theme ]] && pargs+=(-t "$theme")
[[ -n $size ]] && pargs+=(--size "$size")
[[ -f $tmp/config.json ]] && pargs+=(-c "$tmp/config.json")
[[ -z $config || -f $tmp/config.json ]] || pargs+=(-c "$config")
[[ -f $tmp/puppeteer.json ]] && pargs+=(-p "$tmp/puppeteer.json")
pngs=()
if [[ -n $style_file && -n ${PUPPETEER_EXECUTABLE_PATH:-} ]]; then
  # The canvas pattern and rounded frame live on the <svg> root, which mmdc's own PNG export can't style, so
  # screenshot the finished SVG in headless Chrome instead (--size and extra args don't apply).
  for f in "${svgs[@]}"; do
    read -r w h <<< "$(svg_size "$f")"
    "$PUPPETEER_EXECUTABLE_PATH" --headless --no-sandbox --disable-gpu --hide-scrollbars \
      --default-background-color=00000000 --force-device-scale-factor="${scale:-2}" --window-size="$w,$h" \
      --screenshot="${f%.svg}.png" "file://$(cd "$(dirname "$f")" && pwd)/$(basename "$f")" >&2 \
      || die "Chrome failed while rendering PNG of $f" 1
    pngs+=("${f%.svg}.png")
  done
else
  [[ -z $style_file ]] || echo "render.sh: no system Chrome found; the PNG will not have the canvas pattern or rounded frame" >&2
  touch "$tmp/png-start"
  case $input in *.md|*.markdown) sleep 1; pargs+=(-e png) ;; esac
  "${mmdc[@]}" "${pargs[@]}" "${extra[@]}" >&2 || die "mmdc failed while rendering PNG (see the error above)" 1

  case $input in
    *.md|*.markdown)
      while IFS= read -r f; do pngs+=("$f"); done < <(
        find "$artefacts" -maxdepth 1 -name "${stem}-*.png" -newer "$tmp/png-start" | sort -V)
      ;;
    *) pngs=("$pngout") ;;
  esac
fi
[[ ${#pngs[@]} -gt 0 ]] || die "no PNG files were rendered" 3
for f in "${pngs[@]}"; do
  if [[ ! -s $f ]] || [[ $(head -c 4 "$f" | tail -c 3) != PNG ]]; then
    echo "render.sh: $f is empty or not a PNG" >&2; bad=1; continue
  fi
  echo "$f"
done
[[ $bad == 0 ]] || exit 3
