# mermaid-to-svg

Renders Mermaid diagrams to SVG files with [mermaid-cli](https://github.com/mermaid-js/mermaid-cli) (`mmdc`), then checks that the output is valid and actually shows the diagram.

## Triggers

Asks to render, convert, or export Mermaid diagrams as SVG (optionally with PNG or PDF copies, or in a modern Archify-style look), including mermaid blocks in Markdown. See `SKILL.md` for the full list, including when to skip it.

## Install

```bash
/agentic-library use mermaid-to-svg
# or link it manually
ln -s ~/Projects/skills/docs/mermaid-to-svg ~/.claude/skills/mermaid-to-svg
```

## Requirements

- `node` / `npx`. Without `mmdc` on `PATH`, the script runs `npx -y @mermaid-js/mermaid-cli@12.0.0`, which needs network access the first time.
- Chrome or Chromium. If none is found, puppeteer downloads its own copy. `--canvas` PNGs and PDFs need a system Chrome; without one the script warns and falls back to mmdc output with the page colour but no pattern.
- Optional: `xmllint` (XML well-formedness check) and `rsvg-convert` (portability preview).

## Usage

```bash
# Single file -> docs/flow.svg
scripts/render.sh docs/flow.mmd

# Explicit output, portable labels, theme and background
scripts/render.sh --portable -t neutral -b transparent docs/flow.mmd docs/images/flow.svg

# Every mermaid block in a Markdown file -> README-1.svg, README-2.svg, ...
scripts/render.sh README.md docs/images/README.svg

# SVG plus PNG beside it (--scale N sets density, default 2; --size N caps the longest side)
scripts/render.sh --png docs/flow.mmd
scripts/render.sh --scale 3 -b white docs/flow.mmd docs/images/flow.svg

# Modern Archify-style look (dark by default), applied to SVG and PNG
scripts/render.sh --style modern --png docs/flow.mmd
scripts/render.sh --style modern --style-mode light docs/flow.mmd

# Background canvas: blank (default) | dots | grid | blueprint
scripts/render.sh --canvas blueprint --png docs/flow.mmd

# Diagram text from stdin
scripts/render.sh - out/diagram.svg <<'EOF'
sequenceDiagram
  Client->>API: GET /items
EOF
```

## Modern style

`--style modern` restyles the diagram before it is rendered: rounded, tinted nodes, dashed rounded groups, slate edges, a JetBrains Mono font stack with system fallbacks, and a rounded frame around the whole diagram (24px margin, stroked in the style's cluster-border colour), with the background and canvas clipped to it so the corners are transparent. `--style-mode dark|light` (default `dark`) picks the variant. A `-c` config overrides the style, and `-b` overrides the page colour.

`--canvas` (implies `--style modern`) picks the background:

| Canvas | Look |
|--------|------|
| `blank` (default) | Flat page colour: `#020617` dark, `#f4f5f7` light |
| `dots` | 1px dots on a 20px grid |
| `grid` | 40px grid lines |
| `blueprint` | 32px blue grid on deep blue (dark) or pale blue (light) |

The patterns are CSS backgrounds on the SVG root, so Inkscape, rsvg and Office ignore them. PNGs and PDFs are produced from the finished SVG with the system Chrome, so `--size` and extra mmdc arguments don't apply to them.

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | Agent instructions: finding the source, choosing output paths, rendering and checking |
| `scripts/render.sh` | Wrapper around `mmdc` with sanity checks and portability options |
| `styles/modern-{dark,light}.json` | Mermaid config for `--style modern` |
| `styles/canvases.json` | Background canvases (colour and root CSS) for `--canvas`, injected by `render.sh` |
| `references/troubleshooting.md` | Common failures and fixes |
