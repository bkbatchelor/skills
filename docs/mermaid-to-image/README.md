# mermaid-to-image

Turns Mermaid diagrams into SVG files. Mermaid is a text format for describing diagrams. SVG is a picture format that stays sharp at any size. The skill uses [mermaid-cli](https://github.com/mermaid-js/mermaid-cli), a command-line renderer that runs as `mmdc`. It then checks that the SVG is valid and that it shows the diagram.

## Triggers

It starts when you ask to render, convert or export Mermaid diagrams as SVG. It can also make PNG or PDF copies, which are picture and document formats. It can make a modern look, like the one the `archify` skill uses. It also handles Mermaid blocks inside Markdown files. `SKILL.md` lists every trigger phrase and when to skip the skill.

## Install

In Claude Code, type this in the chat:

```text
/agentic-library use mermaid-to-image
```

To install it by hand instead, run this in a terminal. It creates a symlink, which is a shortcut that makes the skill appear in `~/.claude/skills/` without copying it. The path assumes you cloned this repo to `~/Projects/skills`.

```bash
ln -s ~/Projects/skills/docs/mermaid-to-image ~/.claude/skills/mermaid-to-image
```

## Requirements

- **Node.js**, which provides `node` and `npx`. `npx` runs a package without installing it first. If `mmdc` is not on your PATH, the script runs `npx -y @mermaid-js/mermaid-cli@12.0.0`. The first run needs internet access to download that package. PATH is the list of folders your terminal searches for commands.
- **Chrome or Chromium**, a web browser. If the script finds none, puppeteer (a tool that controls a browser) downloads its own copy. PNG and PDF output with `--canvas` needs Chrome on your computer. Without it, the script shows a warning. It then falls back to the mmdc output. That output has the page colour but no background pattern.
- **Optional:** `xmllint`, which checks that an SVG is valid XML. `rsvg-convert` shows how the file looks in other programs.

## Usage

Run these in a terminal:

```bash
# Single file -> docs/flow.svg
scripts/render.sh docs/flow.mmd

# Explicit output, portable labels (text other programs can read), theme and background
scripts/render.sh --portable -t neutral -b transparent docs/flow.mmd docs/images/flow.svg

# Every mermaid block in a Markdown file -> README-1.svg, README-2.svg, ...
scripts/render.sh README.md docs/images/README.svg

# SVG plus PNG beside it (--scale N sets the pixel density, default 2; --size N caps the longest side in pixels)
scripts/render.sh --png docs/flow.mmd
scripts/render.sh --scale 3 -b white docs/flow.mmd docs/images/flow.svg

# Modern look (dark by default), applied to SVG and PNG
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

`--style modern` changes the diagram before it renders. It makes the nodes (boxes) rounded and tinted. It gives groups a dashed, rounded outline. It colours the edges (lines) slate. It sets a JetBrains Mono font with fallbacks. It adds a rounded frame around the whole diagram. The frame has a 24px margin and a border in the colour the style uses for groups. The background is cut to the frame, so the corners are transparent.

`--style-mode dark|light` picks the variant. The default is `dark`. The `-c` option takes a Mermaid config file, and that file overrides the style. The `-b` option replaces the page colour.

`--canvas` sets the background. It also turns on the modern style.

| Canvas | Look |
|--------|------|
| `blank` (default) | A flat page colour: `#020617` dark, `#f4f5f7` light |
| `dots` | 1px dots on a 20px grid |
| `grid` | 40px grid lines |
| `blueprint` | A 32px blue grid on deep blue (dark) or pale blue (light) |

The patterns are CSS (a styling language) backgrounds on the root of the SVG. Inkscape (an SVG editor), rsvg and Office do not show them. PNG and PDF files are made from the finished SVG with the Chrome on your computer. So `--size` and extra mmdc arguments do not apply to them.

## Contents

| Path | Purpose |
|------|---------|
| `SKILL.md` | The instructions: finding the source, choosing output paths, rendering and checking |
| `scripts/render.sh` | A wrapper around `mmdc` with checks and portability options |
| `styles/modern-{dark,light}.json` | Mermaid config for `--style modern` |
| `styles/canvases.json` | Background settings (colour and CSS) for `--canvas`. `render.sh` adds them. |
| `references/troubleshooting.md` | Common failures and how to fix them |
